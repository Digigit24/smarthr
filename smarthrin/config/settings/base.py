"""Base settings shared across all environments."""
import os
from pathlib import Path

import environ

# Base directory is smarthrin/ (project root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["*"]),
    CORS_ALLOWED_ORIGINS=(list, []),
    JWT_ALGORITHM=(str, "HS256"),
)

# Read .env file if it exists
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# Core
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# JWT
JWT_SECRET_KEY = env("JWT_SECRET_KEY", default="change-me-in-production")
JWT_ALGORITHM = env("JWT_ALGORITHM", default="HS256")

# SuperAdmin
SUPERADMIN_URL = env("SUPERADMIN_URL", default="https://admin.celiyo.com")

# Voice AI Orchestrator
VOICE_AI_API_URL = env("VOICE_AI_API_URL", default="http://localhost:4000")
VOICE_AI_API_KEY = env("VOICE_AI_API_KEY", default="")

# How long (in minutes) a CallRecord may stay in an in-flight status
# (QUEUED/INITIATED/RINGING/IN_PROGRESS) before it is considered stale/abandoned.
# Stale records are automatically marked FAILED so a new call can be dispatched,
# which handles the case of missed provider webhooks.
CALL_STALE_THRESHOLD_MINUTES = env.int("CALL_STALE_THRESHOLD_MINUTES", default=5)

# Default country code applied when a phone number is missing the + prefix
# (e.g. legacy/imported applicants saved as "5454210258"). Must include the
# leading "+", e.g. "+91" for India, "+1" for US/Canada.
DEFAULT_PHONE_COUNTRY_CODE = env("DEFAULT_PHONE_COUNTRY_CODE", default="+91")

# Length of a local (subscriber) phone number for the default region. Used to
# disambiguate "10-digit local number that happens to start with the country
# code's digits" from "fully-qualified number with country code embedded".
# Default 10 (Indian mobile, also matches US/Canada).
DEFAULT_PHONE_LOCAL_LENGTH = env.int("DEFAULT_PHONE_LOCAL_LENGTH", default=10)

# Google Calendar (optional — leave blank to disable calendar sync)
# Set CREDENTIALS_JSON to enable. DELEGATE_EMAIL is only needed for Google Workspace.
GOOGLE_CALENDAR_CREDENTIALS_JSON = env("GOOGLE_CALENDAR_CREDENTIALS_JSON", default="")
GOOGLE_CALENDAR_DELEGATE_EMAIL = env("GOOGLE_CALENDAR_DELEGATE_EMAIL", default="")

# Webhooks
WEBHOOK_SECRET = env("WEBHOOK_SECRET", default="")

# AI Screening Thresholds
AUTO_SHORTLIST_THRESHOLD = env.float("AUTO_SHORTLIST_THRESHOLD", default=7.0)
AUTO_REJECT_THRESHOLD = env.float("AUTO_REJECT_THRESHOLD", default=4.0)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    # Local apps
    "common.apps.CommonConfig",
    "jobs.apps.JobsConfig",
    "applicants.apps.ApplicantsConfig",
    "applications.apps.ApplicationsConfig",
    "interviews.apps.InterviewsConfig",
    "calls.apps.CallsConfig",
    "pipeline.apps.PipelineConfig",
    "analytics",
    "webhooks",
    "notifications.apps.NotificationsConfig",
    "integrations",
    "activities",
    "call_queue.apps.CallQueueConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "common.api_logging_middleware.APILoggingMiddleware",
    "django.middleware.common.CommonMiddleware",
    "common.middleware.JWTAuthenticationMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3"),
}

# Cache
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# i18n
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication backends — SuperAdmin API first, then Django model backend as fallback
AUTHENTICATION_BACKENDS = [
    "common.admin_auth_backend.SuperAdminAPIBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["common.authentication.JWTRequestAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardResultsPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "common.exceptions.custom_exception_handler",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# DRF Spectacular — OpenAPI schema generation
SPECTACULAR_SETTINGS = {
    "TITLE": "SmartHR-In API",
    "DESCRIPTION": "HR Recruitment Platform with AI Voice Screening",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "TAGS": [
        {"name": "Jobs", "description": "Job posting management"},
        {"name": "Applicants", "description": "Candidate/applicant records"},
        {"name": "Applications", "description": "Job applications and pipeline"},
        {"name": "Calls", "description": "AI voice screening calls"},
        {"name": "Scorecards", "description": "AI-generated candidate evaluations"},
        {"name": "Interviews", "description": "Interview scheduling"},
        {"name": "Pipeline", "description": "Customizable hiring pipeline stages"},
        {"name": "Analytics", "description": "Recruitment metrics and dashboards"},
        {"name": "Notifications", "description": "In-app notifications"},
        {"name": "Activities", "description": "Audit activity feed"},
        {"name": "Webhooks", "description": "Incoming webhooks from Voice AI"},
        {"name": "Call Queues", "description": "Batch AI screening call queue management"},
        {"name": "Voice Agents", "description": "Voice agent management proxy to CeliyoVoice"},
    ],
    "PREPROCESSING_HOOKS": [],
    "ENUM_NAME_OVERRIDES": {},
}

# CORS
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-tenant-id",
    "x-tenant-slug",
    "tenanttoken",
]

# SendGrid Email
SENDGRID_API_KEY = env("SENDGRID_API_KEY", default="")
SENDGRID_FROM_EMAIL = env("SENDGRID_FROM_EMAIL", default="notifications@smarthr.in")
SENDGRID_FROM_NAME = env("SENDGRID_FROM_NAME", default="SmartHR-In")
# Optional SendGrid dynamic template IDs (leave blank to use Django templates)
SENDGRID_TEMPLATE_NEW_APPLICATION = env("SENDGRID_TEMPLATE_NEW_APPLICATION", default="")
SENDGRID_TEMPLATE_AI_SCREENING_COMPLETE = env("SENDGRID_TEMPLATE_AI_SCREENING_COMPLETE", default="")
SENDGRID_TEMPLATE_INTERVIEW_SCHEDULED = env("SENDGRID_TEMPLATE_INTERVIEW_SCHEDULED", default="")
SENDGRID_TEMPLATE_INTERVIEW_REMINDER = env("SENDGRID_TEMPLATE_INTERVIEW_REMINDER", default="")

# Celery
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Celery Beat schedule for built-in periodic tasks
CELERY_BEAT_SCHEDULE = {
    "tick-running-call-queues": {
        "task": "call_queue.tasks.tick_running_queues",
        "schedule": 60.0,  # Every 60 seconds
        "options": {"expires": 55},  # Expire before next run to prevent pile-up
    },
    "cleanup-stuck-queue-items": {
        "task": "call_queue.tasks.cleanup_stuck_queue_items",
        "schedule": 300.0,  # Every 5 minutes
        "options": {"expires": 290},
    },
    "send-interview-reminders": {
        "task": "notifications.tasks.send_interview_reminders",
        "schedule": 900.0,  # Every 15 minutes
        "options": {"expires": 890},
    },
    "mark-stale-calls-failed": {
        "task": "calls.tasks.mark_stale_calls_failed",
        "schedule": 60.0,  # Every 60 seconds — matches the frontend timer granularity
        "options": {"expires": 55},
    },
}
