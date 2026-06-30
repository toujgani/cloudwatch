from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql://cloudwatch:password@localhost:5432/cloudwatch"

    # OpenStack
    OS_AUTH_URL: str = "http://localhost:5000/v3"
    OS_USERNAME: str = "admin"
    OS_PASSWORD: str = "password"
    OS_PROJECT_NAME: str = "admin"
    OS_USER_DOMAIN_NAME: str = "Default"
    OS_PROJECT_DOMAIN_NAME: str = "Default"

    # OpenShift / Kubernetes
    KUBE_API_URL: str = "https://localhost:6443"
    KUBE_TOKEN: str = ""
    KUBE_VERIFY_SSL: bool = False

    # Collector
    COLLECT_INTERVAL_SECONDS: int = 30

    # JWT
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Alert thresholds
    ALERT_CPU_WARNING: float = 70.0
    ALERT_CPU_CRITICAL: float = 90.0
    ALERT_RAM_WARNING: float = 75.0
    ALERT_RAM_CRITICAL: float = 90.0

    # Email notifications
    EMAIL_ALERTS_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "cloudwatch@localhost"
    ALERT_EMAIL_TO: str = ""
    SMTP_USE_TLS: bool = True

    # Mock mode — test sans OpenStack/OpenShift
    MOCK_MODE: bool = False


settings = Settings()
