import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _derive_key():
    if settings.FERNET_KEY:
        return settings.FERNET_KEY.encode("utf-8")
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_text(value):
    return Fernet(_derive_key()).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(value):
    return Fernet(_derive_key()).decrypt(value.encode("utf-8")).decode("utf-8")

