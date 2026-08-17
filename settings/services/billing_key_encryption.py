"""Billing-key names over the project-wide encryption primitive."""

from core.security.encryption import decrypt_value, encrypt_value


encrypt_billing_key = encrypt_value
decrypt_billing_key = decrypt_value
