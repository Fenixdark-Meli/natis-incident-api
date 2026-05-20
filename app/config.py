from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    APPLICATION: str = "natis-incident-api"
    ENVIRONMENT: str = "development"
    
    # Fury GenAI — injetado automaticamente em produção
    GENAI_SCOPE: str = "prod"
    ANTHROPIC_API_KEY: Optional[str] = None  # fallback local
    GENAI_MODEL: str = "claude-sonnet-4-20250514"
    
    # Atlassian
    ATLASSIAN_URL: str = "https://mercadolibre.atlassian.net"
    ATLASSIAN_CLOUD_ID: str = "a55c251b-e222-488f-8975-3ccdf0a0db6f"
    ATLASSIAN_TOKEN: Optional[str] = None
    
    # Google Drive
    DRIVE_RECORDINGS_FOLDER: str = "1N5h4IluBk3CTR2cpmQH0TQl_4_sQ3k1H"
    DRIVE_NATIS_FOLDER: str = "1kUxGcMk4_p1QGRgoCaVkXiIS_eRSD9UG"
    DRIVE_TOKEN: Optional[str] = None
    
    # Datadog
    DD_API_KEY: Optional[str] = None
    DD_APP_KEY: Optional[str] = None
    DD_SITE: str = "datadoghq.com"
    
    # Slack
    SLACK_TOKEN: Optional[str] = None
    
    # Grid
    GRID_HOST: str = "https://grid.melioffice.com"
    NATIS_EMAIL: str = "danillo.ferreira@mercadolivre.com"
    
    # OTEL
    OTEL_AGENT_ENABLED: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
