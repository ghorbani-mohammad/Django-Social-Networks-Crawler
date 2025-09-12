import os
from datetime import timedelta
from pathlib import Path

import django
import sentry_sdk
from envparse import env
from sentry_sdk.integrations.django import DjangoIntegration

DEBUG = env.bool("DEBUG")
SERVER_IP = env.str("SERVER_IP")
SECRET_KEY = env.str("SECRET_KEY")
BACKEND_URL = env.str("BACKEND_URL")
CSRF_TRUSTED_ORIGINS = [
    f'http://{env.str("ALLOWED_HOSTS")}',
    f'https://{env.str("ALLOWED_HOSTS")}',
]
BASE_DIR = Path(__file__).resolve().parent.parent
ALLOWED_HOSTS = ["localhost", env.str("ALLOWED_HOSTS")]

LOCAL = "local"
PRODUCTION = "production"
ENVIRONMENT = env.str("ENVIRONMENT", default="local")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "network",
    "telegram",
    "linkedin",
    "twitter",
    "notification",
    "ai",
    "user",
    "corsheaders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "social.urls"

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

WSGI_APPLICATION = "social.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "social_db",
        "NAME": "postgres",
        "PORT": 5432,
        "USER": env.str("POSTGRES_USER"),
        "PASSWORD": env.str("POSTGRES_PASSWORD"),
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
if DEBUG:
    STATICFILES_DIRS = (os.path.join(BASE_DIR, "static"),)
else:
    STATIC_ROOT = os.path.join(BASE_DIR, "static")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Celery
BROKER_URL = "redis://social_redis:6379"
CELERY_RESULT_BACKEND = "redis://social_redis:6379"
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Tehran"


CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGIN_REGEXES = ["*"]

# Public API key for read-only endpoints used by public clients
# Set this in environment variables.
PUBLIC_API_KEY = env.str("PUBLIC_API_KEY", default=None)

if (dsn := env.str("SENTRY_DSN", default=None)) is not None:
    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=1.0,
        send_default_pii=True,
        environment="ras-soc",
    )

# Linkedin account auth
LINKEDIN_EMAIL = env.str("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = env.str("LINKEDIN_PASSWORD")

# Telegram account auth
TELEGRAM_API_ID = env.str("TELEGRAM_API_ID")
TELEGRAM_API_HASH = env.str("TELEGRAM_API_HASH")


# Twitter account auth
TWITTER_USERNAME = env.str("TWITTER_USERNAME")
TWITTER_PASSWORD = env.str("TWITTER_PASSWORD")


CACHES = {
    "default": {
        "LOCATION": "redis://social_redis:6379/15",  # Some db numbers already used
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
    },
    "twitter": {
        "LOCATION": "redis://social_redis:6379/5",
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
    },
}


# Email Configs
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST = env("EMAIL_HOST", default=None)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default=None)
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default=None)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Email Logging Configs
SERVER_EMAIL = EMAIL_HOST_USER
ADMIN_EMAIL_LOG = env("ADMIN_EMAIL_LOG", default=None)
LOG_LEVEL = env("LOG_LEVEL", default="ERROR")
ADMINS = (("Log Admin", ADMIN_EMAIL_LOG),)

django.setup()  # we need setup django to have access to apps
# Logging (Just Email Handler)
if EMAIL_HOST_USER and ADMIN_EMAIL_LOG:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {"format": "%(levelname)s %(message)s"},
        },
        "handlers": {
            "mail_admins": {
                "class": "django.utils.log.AdminEmailHandler",
                "formatter": "simple",
                "level": "ERROR",
                # "reporter_class": "reusable.exception_reporter.CustomExceptionReporter",
            },
            "log_db": {
                "class": "reusable.custom_logger.DBHandler",
                "level": "ERROR",
            },
            "log_all_info": {
                "class": "logging.FileHandler",
                "filename": "/app/social/logs/all_info.log",
                "mode": "a",
                "level": "INFO",
            },
            "log_all_error": {
                "class": "logging.FileHandler",
                "filename": "/app/social/logs/all_error.log",
                "mode": "a",
                "level": "ERROR",
            },
            "log_celery_info": {
                "class": "logging.FileHandler",
                "filename": "/app/social/logs/celery_info.log",
                "mode": "a",
                "level": "INFO",
            },
            "log_celery_error": {
                "class": "logging.FileHandler",
                "filename": "/app/social/logs/celery_error.log",
                "mode": "a",
                "level": "ERROR",
            },
        },
        "loggers": {
            # all modules
            "": {
                "handlers": [
                    "mail_admins",
                    "log_db",
                    "log_all_info",
                    "log_all_error",
                ],
                "level": f"{LOG_LEVEL}",
                "propagate": False,
            },
            # celery modules
            "celery": {
                "handlers": [
                    "mail_admins",
                    "log_db",
                    "log_celery_info",
                    "log_celery_error",
                ],
                "level": f"{LOG_LEVEL}",
                "propagate": False,  # if True, will propagate to root logger
            },
        },
    }

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 10,
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=7),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
}

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
