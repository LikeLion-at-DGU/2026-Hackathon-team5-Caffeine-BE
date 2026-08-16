"""billing_key 암호화/복호화. payroll/utils/encryption.py와 동일한 Fernet 방식 재사용."""

from payroll.utils.encryption import decrypt_rrn_front, encrypt_rrn_front

# 함수명은 payroll 도메인 용어지만, 내부적으로 범용 Fernet 암복호화라 그대로 재사용 가능.
encrypt_billing_key = encrypt_rrn_front
decrypt_billing_key = decrypt_rrn_front