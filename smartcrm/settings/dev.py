from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool("DEBUG", default=True)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or "django-insecure-dev-only-change-me"

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


try:
    from .local import *
except ImportError:
    pass
