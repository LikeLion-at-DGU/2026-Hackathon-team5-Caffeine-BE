"""encrypt_with_public_key()가 공식 CODEF SDK(easycodefpy)의 RSA 암호화 방식과
호환되는지 검증한다.

easycodefpy.util.encrypt_rsa()는 PyPI에 공개된 easycodefpy 패키지(1.0.1)에서
직접 확인한 구현이다:

    def encrypt_rsa(text: str, public_key: str) -> str:
        key_der = base64.b64decode(public_key)
        key_pub = RSA.importKey(key_der)
        cipher = PKCS1.new(key_pub)  # Crypto.Cipher.PKCS1_v1_5
        cipher_text = cipher.encrypt(text.encode())
        return base64.b64encode(cipher_text).decode('utf-8')

우리 encrypt_with_public_key()는 이 구현과 동일한 라이브러리(pycryptodome의
RSA/PKCS1_v1_5)를 그대로 사용하므로, 여기서는 "우리가 암호화한 값을 진짜
개인키로 복호화하면 원문이 그대로 나오는지"를 검증해 CODEF 서버가 실제로
이 값을 해독할 수 있는 형태인지 확인한다.
"""

import base64

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA
from django.test import SimpleTestCase, override_settings

from integrations.codef.client import CodefClientError, encrypt_with_public_key


def _generate_test_keypair():
    """테스트용 RSA 키쌍을 만든다. CODEF가 실제로 주는 키가 아니라, 우리
    암호화 결과를 대응하는 개인키로 복호화할 수 있는지만 확인하는 용도다."""
    key = RSA.generate(2048)
    public_key_b64 = base64.b64encode(key.publickey().export_key(format="DER")).decode("utf-8")
    return key, public_key_b64


class EncryptWithPublicKeyTests(SimpleTestCase):
    def setUp(self):
        self.private_key, self.public_key_b64 = _generate_test_keypair()

    def test_missing_public_key_raises_codef_client_error(self):
        with override_settings(CODEF_PUBLIC_KEY=""):
            with self.assertRaises(CodefClientError):
                encrypt_with_public_key("1234567890")

    def test_invalid_public_key_raises_codef_client_error_not_raw_crypto_exception(self):
        with override_settings(CODEF_PUBLIC_KEY="this-is-not-a-valid-der-key"):
            with self.assertRaises(CodefClientError):
                encrypt_with_public_key("1234567890")

    def test_encrypted_value_round_trips_through_real_private_key(self):
        plaintext = "1234567890"
        with override_settings(CODEF_PUBLIC_KEY=self.public_key_b64):
            ciphertext_b64 = encrypt_with_public_key(plaintext)

        # 우리 코드는 개인키를 모르니, 테스트에서 만든 개인키로 직접 복호화해
        # CODEF 서버(공식 SDK와 같은 방식)가 이 값을 풀 수 있는지 확인한다.
        cipher = PKCS1_v1_5.new(self.private_key)
        sentinel = object()
        decrypted = cipher.decrypt(base64.b64decode(ciphertext_b64), sentinel)

        self.assertEqual(decrypted.decode("utf-8"), plaintext)

    def test_result_is_base64_and_differs_each_call(self):
        # PKCS1v1.5는 매번 랜덤 패딩을 쓰므로, 같은 평문도 호출마다 암호문이
        # 달라야 한다 — 같으면 패딩이 빠진 것이므로 오히려 버그다.
        with override_settings(CODEF_PUBLIC_KEY=self.public_key_b64):
            first = encrypt_with_public_key("1234567890")
            second = encrypt_with_public_key("1234567890")

        self.assertNotEqual(first, second)
        # 둘 다 유효한 base64여야 한다 (실패하면 예외가 난다).
        base64.b64decode(first)
        base64.b64decode(second)

    def test_korean_text_round_trips(self):
        # userName처럼 한글이 들어갈 수도 있는 값도 안전하게 처리돼야 한다.
        plaintext = "김지훈"
        with override_settings(CODEF_PUBLIC_KEY=self.public_key_b64):
            ciphertext_b64 = encrypt_with_public_key(plaintext)

        cipher = PKCS1_v1_5.new(self.private_key)
        sentinel = object()
        decrypted = cipher.decrypt(base64.b64decode(ciphertext_b64), sentinel)

        self.assertEqual(decrypted.decode("utf-8"), plaintext)