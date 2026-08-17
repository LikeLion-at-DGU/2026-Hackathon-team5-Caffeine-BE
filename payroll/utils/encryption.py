"""Payroll-specific names kept over the project-wide encryption primitive."""

from core.security.encryption import decrypt_value, encrypt_value


encrypt_rrn_front = encrypt_value
decrypt_rrn_front = decrypt_value
