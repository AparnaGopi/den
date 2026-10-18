"""Deployment settings. Keep developer settings in config.settings."""

import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Set {name} in the hosting environment.")
    return value


def csv_setting(name, default=""):
    return [value.strip() for value in os.environ.get(name, default).split(",") if value.strip()]


DEBUG = False
SECRET_KEY = required("DJANGO_SECRET_KEY")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a new random secret of at least 50 characters.")

ALLOWED_HOSTS = csv_setting("DJANGO_ALLOWED_HOSTS")
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must list the actual deployment hostnames.")
CSRF_TRUSTED_ORIGINS = csv_setting("DJANGO_CSRF_TRUSTED_ORIGINS")
if render_hostname:
    CSRF_TRUSTED_ORIGINS.append(f"https://{render_hostname}")
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = csv_setting("DJANGO_CORS_ALLOWED_ORIGINS")

DATABASES = {"default": dj_database_url.parse(required("DATABASE_URL"), conn_max_age=60, conn_health_checks=True)}

MIDDLEWARE = list(MIDDLEWARE)  # noqa: F405
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405
STATIC_URL = "/static/"
STORAGES = {**STORAGES, "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}  # noqa: F405
if os.environ.get("DEN_MEDIA_ROOT"):
    MEDIA_ROOT = Path(os.environ["DEN_MEDIA_ROOT"])  # noqa: F405

# The hosting proxy must replace untrusted incoming X-Forwarded-Proto headers.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True

ROOT_URLCONF = "config.urls_deploy"
DEN_ALLOW_LOCAL_DEMO_VENDOR_SEED = False

DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "Den <noreply@torontodecorden.com>")
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": os.environ.get("DJANGO_EMAIL_HOST", "localhost"),
            "port": int(os.environ.get("DJANGO_EMAIL_PORT", "587")),
            "username": os.environ.get("DJANGO_EMAIL_USERNAME", ""),
            "password": os.environ.get("DJANGO_EMAIL_PASSWORD", ""),
            "use_tls": True,
            "timeout": 15,
        },
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
