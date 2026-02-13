"""
AWS SSO Token Auto-Refresh Utility.

Proactively refreshes the SSO access token using the long-lived refresh token
so the MCP subprocess always has valid credentials. This eliminates the need
for daily `aws sso login` — you only need to re-login when the refresh token
itself expires (~90 days).
"""
import json
import logging
import os
import glob
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple

import boto3

logger = logging.getLogger(__name__)

# How many minutes before expiry should we proactively refresh?
REFRESH_BUFFER_MINUTES = 15


def _get_sso_cache_dir() -> Path:
    """Get the AWS SSO cache directory."""
    return Path.home() / ".aws" / "sso" / "cache"


def _load_sso_token_file() -> Tuple[Optional[dict], Optional[Path]]:
    """
    Find and load the SSO token cache file that contains the access token
    and refresh token.

    Returns:
        Tuple of (token_data, file_path) or (None, None) if not found.
    """
    cache_dir = _get_sso_cache_dir()
    if not cache_dir.exists():
        logger.warning("SSO cache directory not found: %s", cache_dir)
        return None, None

    # Look through all cache files for one with a refreshToken
    best_file = None
    best_data = None
    best_time = None

    for cache_file in cache_dir.glob("*.json"):
        try:
            data = json.loads(cache_file.read_text())
            # We want the file that has both accessToken and refreshToken
            if data.get("accessToken") and data.get("refreshToken"):
                mtime = cache_file.stat().st_mtime
                if best_time is None or mtime > best_time:
                    best_file = cache_file
                    best_data = data
                    best_time = mtime
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Skipping cache file %s: %s", cache_file.name, e)
            continue

    if best_data:
        logger.debug("Found SSO token in %s", best_file.name)
    else:
        logger.warning("No SSO token cache file with refresh token found")

    return best_data, best_file


def _load_client_registration() -> Optional[dict]:
    """
    Find and load the OIDC client registration cache file.
    This contains clientId and clientSecret needed for token refresh.

    Returns:
        Client registration data dict, or None if not found.
    """
    cache_dir = _get_sso_cache_dir()
    if not cache_dir.exists():
        return None

    for cache_file in cache_dir.glob("*.json"):
        try:
            data = json.loads(cache_file.read_text())
            # Client registration files have clientId and clientSecret
            # but do NOT have accessToken
            if (data.get("clientId") and data.get("clientSecret")
                    and not data.get("accessToken")):
                logger.debug("Found client registration in %s", cache_file.name)
                return data
        except (json.JSONDecodeError, OSError):
            continue

    logger.warning("No OIDC client registration found in SSO cache")
    return None


def _parse_expiry(expires_at: str) -> datetime:
    """Parse an ISO 8601 expiry timestamp from AWS."""
    # Handle both 'Z' suffix and '+00:00' formats
    expires_at = expires_at.replace("Z", "+00:00")
    return datetime.fromisoformat(expires_at)


def _is_token_expired(token_data: dict, buffer_minutes: int = REFRESH_BUFFER_MINUTES) -> bool:
    """
    Check if the access token is expired or about to expire.

    Args:
        token_data: The SSO token cache data.
        buffer_minutes: Refresh this many minutes before actual expiry.

    Returns:
        True if token needs refreshing.
    """
    expires_at = token_data.get("expiresAt")
    if not expires_at:
        return True

    try:
        expiry = _parse_expiry(expires_at)
        now = datetime.now(timezone.utc)
        return now >= (expiry - timedelta(minutes=buffer_minutes))
    except (ValueError, TypeError):
        logger.warning("Could not parse token expiry: %s", expires_at)
        return True


def _refresh_access_token(
    token_data: dict,
    client_registration: dict,
    sso_region: str = "us-west-2",
) -> Optional[dict]:
    """
    Use the refresh token to obtain a new access token from AWS SSO OIDC.

    Args:
        token_data: Current SSO token cache data (must contain refreshToken).
        client_registration: OIDC client registration data.
        sso_region: AWS region for the SSO OIDC endpoint.

    Returns:
        New token response dict from OIDC, or None on failure.
    """
    refresh_token = token_data.get("refreshToken")
    client_id = client_registration.get("clientId")
    client_secret = client_registration.get("clientSecret")

    if not all([refresh_token, client_id, client_secret]):
        logger.error("Missing required fields for token refresh")
        return None

    try:
        # Use a bare boto3 client (no profile) — we're calling the OIDC
        # endpoint directly, not using the expired SSO credentials.
        oidc_client = boto3.client(
            "sso-oidc",
            region_name=sso_region,
        )

        response = oidc_client.create_token(
            clientId=client_id,
            clientSecret=client_secret,
            grantType="refresh_token",
            refreshToken=refresh_token,
        )

        logger.info("Successfully refreshed SSO access token")
        return response

    except Exception as e:
        logger.error("Failed to refresh SSO access token: %s", e)
        return None


def _update_cache_file(
    cache_path: Path,
    original_data: dict,
    oidc_response: dict,
) -> bool:
    """
    Write the refreshed token data back to the SSO cache file.

    Args:
        cache_path: Path to the cache JSON file.
        original_data: Original cache data (to preserve fields like startUrl).
        oidc_response: Response from OIDC CreateToken call.

    Returns:
        True if successfully written.
    """
    try:
        new_access_token = oidc_response.get("accessToken")
        expires_in = oidc_response.get("expiresIn", 28800)  # seconds
        new_refresh_token = oidc_response.get("refreshToken")

        if not new_access_token:
            logger.error("OIDC response missing accessToken")
            return False

        # Calculate new expiry
        new_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Update the cached data
        updated = dict(original_data)
        updated["accessToken"] = new_access_token
        updated["expiresAt"] = new_expiry.strftime("%Y-%m-%dT%H:%M:%SZ")

        # OIDC may return a new refresh token (rotation)
        if new_refresh_token:
            updated["refreshToken"] = new_refresh_token

        cache_path.write_text(json.dumps(updated, indent=2))
        logger.info(
            "Updated SSO cache — new token expires at %s",
            updated["expiresAt"],
        )
        return True

    except Exception as e:
        logger.error("Failed to update SSO cache file: %s", e)
        return False


# ------------------------------------------------------------------ #
#  Public API                                                         #
# ------------------------------------------------------------------ #


def ensure_sso_credentials(sso_region: str = "us-west-2") -> bool:
    """
    Check SSO credentials and refresh if needed.

    This is the main function to call — it's safe to call frequently.
    It's a no-op if the token is still valid.

    Args:
        sso_region: AWS region for the SSO OIDC endpoint.

    Returns:
        True if credentials are valid (or were successfully refreshed).
        False if credentials are invalid and could not be refreshed.
    """
    token_data, cache_path = _load_sso_token_file()
    if not token_data or not cache_path:
        logger.error(
            "No SSO token cache found. "
            "Run: aws sso login --profile DtcReadOnly-017521386069"
        )
        return False

    # Check if token is still valid
    if not _is_token_expired(token_data):
        logger.debug("SSO access token is still valid")
        return True

    logger.info("SSO access token expired or expiring soon — refreshing...")

    # Load client registration
    client_reg = _load_client_registration()
    if not client_reg:
        logger.error(
            "No OIDC client registration found. "
            "Run: aws sso login --profile DtcReadOnly-017521386069"
        )
        return False

    # Check if client registration itself is expired
    client_expiry = client_reg.get("expiresAt")
    if client_expiry:
        try:
            if _parse_expiry(client_expiry) < datetime.now(timezone.utc):
                logger.error(
                    "OIDC client registration expired at %s. "
                    "Run: aws sso login --profile DtcReadOnly-017521386069",
                    client_expiry,
                )
                return False
        except (ValueError, TypeError):
            pass

    # Attempt refresh
    oidc_response = _refresh_access_token(token_data, client_reg, sso_region)
    if not oidc_response:
        logger.error(
            "Token refresh failed. "
            "Run: aws sso login --profile DtcReadOnly-017521386069"
        )
        return False

    # Write refreshed token back to cache
    return _update_cache_file(cache_path, token_data, oidc_response)


def check_sso_status(sso_region: str = "us-west-2") -> dict:
    """
    Get the current status of SSO credentials.

    Returns:
        Dict with status info: token_valid, access_token_expiry,
        refresh_token_present, client_registration_expiry, message.
    """
    result = {
        "token_valid": False,
        "access_token_expiry": None,
        "refresh_token_present": False,
        "client_registration_expiry": None,
        "message": "",
    }

    token_data, _ = _load_sso_token_file()
    if not token_data:
        result["message"] = (
            "No SSO credentials found. "
            "Run: aws sso login --profile DtcReadOnly-017521386069"
        )
        return result

    # Access token info
    expires_at = token_data.get("expiresAt", "")
    result["access_token_expiry"] = expires_at
    result["refresh_token_present"] = bool(token_data.get("refreshToken"))
    result["token_valid"] = not _is_token_expired(token_data, buffer_minutes=0)

    # Client registration info
    client_reg = _load_client_registration()
    if client_reg:
        result["client_registration_expiry"] = client_reg.get("expiresAt")

    # Generate message
    if result["token_valid"]:
        try:
            expiry = _parse_expiry(expires_at)
            remaining = expiry - datetime.now(timezone.utc)
            hours = remaining.total_seconds() / 3600
            result["message"] = f"SSO credentials valid — expires in {hours:.1f} hours"
        except (ValueError, TypeError):
            result["message"] = "SSO credentials appear valid"
    elif result["refresh_token_present"]:
        result["message"] = "SSO access token expired — auto-refresh available"
    else:
        result["message"] = (
            "SSO credentials expired and no refresh token. "
            "Run: aws sso login --profile DtcReadOnly-017521386069"
        )

    return result
