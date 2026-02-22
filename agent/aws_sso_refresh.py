"""
AWS SSO Token Auto-Refresh Utility.

Proactively refreshes the SSO access token using the OIDC refresh token.
If the refresh token itself is invalid/expired, falls back to running
`aws sso login` automatically (non-interactive device code flow).
"""
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple

import boto3

logger = logging.getLogger(__name__)

# How many minutes before expiry should we proactively refresh?
REFRESH_BUFFER_MINUTES = 15

# Default SSO profile name
DEFAULT_SSO_PROFILE = "DtcReadOnly-017521386069"


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

    best_file = None
    best_data = None
    best_time = None

    for cache_file in cache_dir.glob("*.json"):
        try:
            data = json.loads(cache_file.read_text())
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
    """
    cache_dir = _get_sso_cache_dir()
    if not cache_dir.exists():
        return None

    for cache_file in cache_dir.glob("*.json"):
        try:
            data = json.loads(cache_file.read_text())
            if (data.get("clientId") and data.get("clientSecret")
                    and not data.get("accessToken")):
                return data
        except (json.JSONDecodeError, OSError):
            continue

    return None


def _parse_expiry(expires_at: str) -> datetime:
    """Parse an ISO 8601 expiry timestamp from AWS."""
    expires_at = expires_at.replace("Z", "+00:00")
    return datetime.fromisoformat(expires_at)


def _is_token_expired(token_data: dict, buffer_minutes: int = REFRESH_BUFFER_MINUTES) -> bool:
    """Check if the access token is expired or about to expire."""
    expires_at = token_data.get("expiresAt")
    if not expires_at:
        return True
    try:
        expiry = _parse_expiry(expires_at)
        now = datetime.now(timezone.utc)
        return now >= (expiry - timedelta(minutes=buffer_minutes))
    except (ValueError, TypeError):
        return True


def _refresh_via_oidc(
    token_data: dict,
    client_registration: dict,
    sso_region: str = "us-west-2",
) -> Optional[dict]:
    """
    Use the refresh token to obtain a new access token from AWS SSO OIDC.
    Returns new token response dict, or None on failure.
    """
    refresh_token = token_data.get("refreshToken")
    client_id = client_registration.get("clientId")
    client_secret = client_registration.get("clientSecret")

    if not all([refresh_token, client_id, client_secret]):
        return None

    try:
        oidc_client = boto3.client("sso-oidc", region_name=sso_region)
        response = oidc_client.create_token(
            clientId=client_id,
            clientSecret=client_secret,
            grantType="refresh_token",
            refreshToken=refresh_token,
        )
        logger.info("Successfully refreshed SSO access token via OIDC")
        return response
    except Exception as e:
        logger.warning("OIDC token refresh failed: %s", e)
        return None


def _update_cache_file(
    cache_path: Path,
    original_data: dict,
    oidc_response: dict,
) -> bool:
    """Write the refreshed token data back to the SSO cache file."""
    try:
        new_access_token = oidc_response.get("accessToken")
        expires_in = oidc_response.get("expiresIn", 28800)
        new_refresh_token = oidc_response.get("refreshToken")

        if not new_access_token:
            return False

        new_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        updated = dict(original_data)
        updated["accessToken"] = new_access_token
        updated["expiresAt"] = new_expiry.strftime("%Y-%m-%dT%H:%M:%SZ")

        if new_refresh_token:
            updated["refreshToken"] = new_refresh_token

        cache_path.write_text(json.dumps(updated, indent=2))
        logger.info("Updated SSO cache — new token expires at %s", updated["expiresAt"])
        return True
    except Exception as e:
        logger.error("Failed to update SSO cache file: %s", e)
        return False


def _run_sso_login(profile: str = DEFAULT_SSO_PROFILE) -> bool:
    """
    Run `aws sso login` as a subprocess. This will:
    - Open a browser for authentication (if needed)
    - Or use device-code flow if no browser is available

    Returns True if login succeeded.
    """
    logger.info("Running `aws sso login --profile %s` ...", profile)
    try:
        result = subprocess.run(
            ["aws", "sso", "login", "--profile", profile],
            capture_output=False,  # Let user see the output / browser prompt
            timeout=120,  # 2-minute timeout
        )
        if result.returncode == 0:
            logger.info("aws sso login completed successfully")
            return True
        else:
            logger.error("aws sso login exited with code %d", result.returncode)
            return False
    except subprocess.TimeoutExpired:
        logger.error("aws sso login timed out after 120 seconds")
        return False
    except FileNotFoundError:
        logger.error("aws CLI not found. Install it from https://aws.amazon.com/cli/")
        return False
    except Exception as e:
        logger.error("aws sso login failed: %s", e)
        return False


def _verify_credentials(profile: str = DEFAULT_SSO_PROFILE) -> bool:
    """Quick check: can we call STS with this profile?"""
    try:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--profile", profile],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


# ------------------------------------------------------------------ #
#  Public API                                                         #
# ------------------------------------------------------------------ #


def ensure_sso_credentials(
    sso_region: str = "us-west-2",
    profile: str = DEFAULT_SSO_PROFILE,
    auto_login: bool = True,
) -> bool:
    """
    Ensure SSO credentials are valid. Attempts in order:

    1. Check if current access token is still valid → return True
    2. Try OIDC refresh token → return True if it worked
    3. (if auto_login) Run `aws sso login` automatically → return True if it worked
    4. Return False (needs manual intervention)

    Args:
        sso_region: AWS region for SSO OIDC endpoint.
        profile: AWS CLI profile name for fallback login.
        auto_login: If True, automatically run `aws sso login` when
                    the refresh token is also invalid.

    Returns:
        True if credentials are now valid.
    """
    # Step 1: Check current token
    token_data, cache_path = _load_sso_token_file()
    if token_data and cache_path and not _is_token_expired(token_data):
        logger.debug("SSO access token is still valid")
        return True

    # Step 2: Try OIDC refresh
    if token_data and cache_path:
        client_reg = _load_client_registration()
        if client_reg:
            client_expiry = client_reg.get("expiresAt")
            client_valid = True
            if client_expiry:
                try:
                    client_valid = _parse_expiry(client_expiry) > datetime.now(timezone.utc)
                except (ValueError, TypeError):
                    pass

            if client_valid:
                oidc_response = _refresh_via_oidc(token_data, client_reg, sso_region)
                if oidc_response and _update_cache_file(cache_path, token_data, oidc_response):
                    return True

        logger.warning("OIDC refresh token is invalid or expired")

    # Step 3: Fallback to aws sso login
    if auto_login:
        logger.info(
            "Falling back to `aws sso login` — "
            "this will open your browser for authentication"
        )
        if _run_sso_login(profile):
            # Verify it actually worked
            if _verify_credentials(profile):
                return True
            else:
                logger.error("aws sso login completed but credentials still invalid")

    logger.error(
        "Unable to obtain valid SSO credentials. "
        "Manually run: aws sso login --profile %s", profile,
    )
    return False


def check_sso_status(sso_region: str = "us-west-2") -> dict:
    """
    Get the current status of SSO credentials.

    Returns dict with: token_valid, access_token_expiry,
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
            "Run: aws sso login --profile " + DEFAULT_SSO_PROFILE
        )
        return result

    expires_at = token_data.get("expiresAt", "")
    result["access_token_expiry"] = expires_at
    result["refresh_token_present"] = bool(token_data.get("refreshToken"))
    result["token_valid"] = not _is_token_expired(token_data, buffer_minutes=0)

    client_reg = _load_client_registration()
    if client_reg:
        result["client_registration_expiry"] = client_reg.get("expiresAt")

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
            "Run: aws sso login --profile " + DEFAULT_SSO_PROFILE
        )

    return result
