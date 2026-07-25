from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

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
    KUBE_NAMESPACE: str = ""  # if set, only monitor this namespace

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

    # Grafana API
    GRAFANA_URL: str = "http://localhost:3000"
    GRAFANA_API_TOKEN: str = ""
    GRAFANA_METRICS_DATASOURCE_UID: str = ""
    GRAFANA_LOGS_DATASOURCE_UID: str = ""
    GRAFANA_TRACES_DATASOURCE_UID: str = ""
    GRAFANA_VERIFY_SSL: bool = True

    # Financial dashboard assumptions
    FINANCE_MONTHLY_INFRA_COST: float = 10000.0
    FINANCE_AUTOMATION_SAVINGS_RATE: float = 0.12

    # AI remediation guardrails
    AUTO_REMEDIATION_ENABLED: bool = True
    AUTO_REMEDIATION_DRY_RUN: bool = True
    AUTO_REMEDIATION_MIN_SCORE: int = 55
    REMEDIATION_STORAGE_INCREMENT_GB: int = 20
    REMEDIATION_MEMORY_SCALE_PERCENT: int = 25
    REMEDIATION_MAX_ACTIONS_PER_HOUR: int = 5
    REMEDIATION_MAX_STORAGE_GB: int = 500
    REMEDIATION_MEMORY_FLAVOR_MAP: str = "{}"
    REMEDIATION_VM_RECOVERY_ACTION: str = "hard_reboot"  # hard_reboot | stop | live_migrate
    REMEDIATION_K8S_SAFE_NAMESPACES: str = "default"

    # Soft Quota (percentage of actual sandbox quota to use as operating limit)
    SOFT_QUOTA_CPU_PERCENT: int = 90
    SOFT_QUOTA_RAM_PERCENT: int = 90
    QUOTA_THRESHOLD_WARNING: int = 80
    QUOTA_THRESHOLD_CRITICAL: int = 90
    QUOTA_THRESHOLD_REMEDIATE: int = 95

    # Branding
    BRANDING_STORAGE_PATH: str = "/app/branding"

    # Production settings
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = ""


settings = Settings()
