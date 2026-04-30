from datetime import timedelta
from pathlib import Path
import os
import sys

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "accounts.apps.AccountsConfig",
    "shop.apps.ShopConfig",
    "orders.apps.OrdersConfig",
    "payments.apps.PaymentsConfig",
    "admin_console.apps.AdminConsoleConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.middleware.RequestLoggingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

def _default_db_engine(argv=None):
    argv = argv if argv is not None else sys.argv
    executable = Path(str(argv[0])).stem.lower() if argv else ""
    management_command = str(argv[1]).lower() if len(argv) > 1 else ""
    if executable in {"pytest", "py.test"} or management_command == "test":
        return "sqlite"
    return "mysql"


DB_ENGINE = os.getenv("DB_ENGINE", _default_db_engine()).lower()

if DB_ENGINE == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "cardshop"),
            "USER": os.getenv("DB_USER", "cardshop"),
            "PASSWORD": os.getenv("DB_PASSWORD", "cardshop"),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
elif DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    raise RuntimeError(f"Unsupported DB_ENGINE: {DB_ENGINE}")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
if DEBUG:
    STORAGES = {
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        }
    }
else:
    STORAGES = {
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CORS_ALLOW_ALL_ORIGINS = DEBUG and not CORS_ALLOWED_ORIGINS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
}

redis_url = os.getenv("REDIS_URL")
if redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": redis_url,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND")
if not EMAIL_BACKEND:
    EMAIL_BACKEND = (
        "django.core.mail.backends.smtp.EmailBackend"
        if os.getenv("EMAIL_HOST")
        else "django.core.mail.backends.console.EmailBackend"
    )
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "noreply@example.com")

SITE_URL = os.getenv("SITE_URL", "http://localhost:5173").rstrip("/")
FERNET_KEY = os.getenv("FERNET_KEY", "")
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "dev").lower()
EASYPAY_PID = os.getenv("EASYPAY_PID", "")
EASYPAY_KEY = os.getenv("EASYPAY_KEY", "")
EASYPAY_GATEWAY_URL = os.getenv("EASYPAY_GATEWAY_URL", "").rstrip("/")
ALIPAY_APP_ID = os.getenv("ALIPAY_APP_ID", "")
ALIPAY_APP_PRIVATE_KEY = os.getenv("ALIPAY_APP_PRIVATE_KEY", "")
ALIPAY_PUBLIC_KEY = os.getenv("ALIPAY_PUBLIC_KEY", "")
ALIPAY_GATEWAY_URL = os.getenv(
    "ALIPAY_GATEWAY_URL",
    "https://openapi-sandbox.dl.alipaydev.com/gateway.do",
).rstrip("/")
ALIPAY_NOTIFY_URL = os.getenv("ALIPAY_NOTIFY_URL", "")
ALIPAY_RETURN_URL = os.getenv("ALIPAY_RETURN_URL", "")
ORDER_RESERVE_MINUTES = int(os.getenv("ORDER_RESERVE_MINUTES", "15"))
SLOW_REQUEST_MS = int(os.getenv("SLOW_REQUEST_MS", "1000"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_TO_FILE = env_bool("LOG_TO_FILE", not DEBUG)
LOG_DIR = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

if LOG_TO_FILE:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)


def _file_handler(filename, level):
    if not LOG_TO_FILE:
        return {"class": "logging.NullHandler"}
    return {
        "class": "logging.handlers.RotatingFileHandler",
        "level": level,
        "formatter": "standard",
        "filters": ["request_context"],
        "filename": str(Path(LOG_DIR) / filename),
        "maxBytes": LOG_MAX_BYTES,
        "backupCount": LOG_BACKUP_COUNT,
        "encoding": "utf-8",
    }


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_context": {
            "()": "config.logging_context.RequestContextFilter",
        },
    },
    "formatters": {
        "standard": {
            "format": (
                "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s "
                "user_id=%(user_id)s client_ip=%(client_ip)s %(message)s"
            )
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": LOG_LEVEL,
            "formatter": "standard",
            "filters": ["request_context"],
        },
        "app_file": _file_handler("app.log", LOG_LEVEL),
        "error_file": _file_handler("error.log", "ERROR"),
        "security_file": _file_handler("security.log", "WARNING"),
    },
    "root": {
        "handlers": ["console", "app_file", "error_file"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "cardshop.request": {
            "handlers": ["console", "app_file", "error_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "cardshop.orders": {
            "handlers": ["console", "app_file", "error_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "cardshop.payments": {
            "handlers": ["console", "app_file", "error_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "cardshop.payments.notify": {
            "handlers": ["console", "app_file", "error_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "cardshop.security": {
            "handlers": ["console", "app_file", "error_file", "security_file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
