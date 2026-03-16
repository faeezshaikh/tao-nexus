"""
Configuration management for the FastAPI agent.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings."""
    
    # Ollama Configuration
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "https://ollama.services.tirescorp.com")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama2")
    ollama_api_key: Optional[str] = os.getenv("OLLAMA_API_KEY", None)
    ollama_timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    
    # MCP Server Configuration
    mcp_server_command: str = os.getenv("MCP_SERVER_COMMAND", "uvx")
    mcp_server_args: str = os.getenv("MCP_SERVER_ARGS", "mcp-server-aws-cost-explorer")
    
    # API Configuration
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    api_reload: bool = os.getenv("API_RELOAD", "true").lower() == "true"
    
    # CORS Configuration
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")
    
    @property
    def cors_origins_list(self) -> list:
        """Convert CORS origins string to list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    # Logging Configuration
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # AWS Configuration
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    aws_profile: Optional[str] = os.getenv("AWS_PROFILE", None)
    aws_access_key_id: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID", None)
    aws_secret_access_key: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY", None)
    aws_session_token: Optional[str] = os.getenv("AWS_SESSION_TOKEN", None)
    aws_target_role_arn: Optional[str] = os.getenv("AWS_TARGET_ROLE_ARN", None)

    # Nexus Configuration
    nexus_mock_mode: bool = os.getenv("NEXUS_MOCK_MODE", "true").lower() == "true"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra fields in .env file


# Global settings instance
settings = Settings()
