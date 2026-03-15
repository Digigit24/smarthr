"""Development settings."""
from .base import *  # noqa: F401, F403

DEBUG = True

INSTALLED_APPS += [  # noqa: F405
    "django.contrib.admindocs",
]

# Use console email backend in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

# Looser logging in development
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "smarthrin": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
