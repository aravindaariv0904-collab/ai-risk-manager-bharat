from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    SUPABASE_URL: str = "https://placeholder.supabase.co"
    SUPABASE_SERVICE_ROLE_KEY: str = "placeholder"
    SUPABASE_ANON_KEY: str = "placeholder"
    SUPABASE_JWT_SECRET: str = "placeholder"

    RAZORPAY_KEY_ID: str = "rzp_test_placeholder"
    RAZORPAY_KEY_SECRET: str = "placeholder"
    RAZORPAY_WEBHOOK_SECRET: str = "placeholder"

    GEMINI_API_KEY: str = "placeholder"

    # Stored as str in .env, parsed into list by validator
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:3111"

    DEMO_MODE: bool = True
    DEMO_USER_EMAIL: str = "user@example.com"
    DEMO_VENDOR_EMAIL: str = "vendor@example.com"

    def get_cors_origins(self) -> List[str]:
        """Parse CORS_ORIGINS string into a list."""
        v = self.CORS_ORIGINS
        if not v:
            return ["http://localhost:3111"]
        if v.startswith("["):
            import json
            try:
                return json.loads(v)
            except Exception:
                pass
        return [origin.strip() for origin in v.split(",") if origin.strip()]


settings = Settings()