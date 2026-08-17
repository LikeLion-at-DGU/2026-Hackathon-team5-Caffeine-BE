from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet() -> Fernet:
    key = settings.APP_ENCRYPTION_KEY
    if not key:
        raise ValueError("APP_ENCRYPTION_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_value(plain_text: str) -> str:
    if not plain_text:
        return ""
    return _get_fernet().encrypt(plain_text.encode()).decode()


def decrypt_value(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    return _get_fernet().decrypt(cipher_text.encode()).decode()
