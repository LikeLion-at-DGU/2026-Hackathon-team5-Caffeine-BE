"""공통 암호화 모듈을 빌링키 용어로 감싼다."""

from core.security.encryption import decrypt_value, encrypt_value


encrypt_billing_key = encrypt_value
decrypt_billing_key = decrypt_value
