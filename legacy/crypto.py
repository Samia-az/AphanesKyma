import os
from hashlib import sha256

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoManager:

    SALT_SIZE = 16
    NONCE_SIZE = 12

    def _create_key(self, password, salt):

        password_bytes = password.encode("utf-8")

        return sha256(
            password_bytes + salt
        ).digest()


    # =========================================
    # Encrypt bytes
    # =========================================

    def encrypt_bytes(self, data, password):

        salt = os.urandom(
            self.SALT_SIZE
        )

        key = self._create_key(
            password,
            salt
        )

        nonce = os.urandom(
            self.NONCE_SIZE
        )

        aes = AESGCM(key)

        ciphertext = aes.encrypt(
            nonce,
            data,
            None
        )

        # salt + nonce + ciphertext
        return (
            salt
            + nonce
            + ciphertext
        )


    # =========================================
    # Decrypt bytes
    # =========================================

    def decrypt_bytes(
        self,
        encrypted_data,
        password
    ):

        if len(encrypted_data) < 28:

            raise ValueError(
                "Encrypted data is invalid."
            )

        salt = encrypted_data[:16]

        nonce = encrypted_data[16:28]

        ciphertext = encrypted_data[28:]

        key = self._create_key(
            password,
            salt
        )

        aes = AESGCM(key)

        return aes.decrypt(
            nonce,
            ciphertext,
            None
        )


    # =========================================
    # Encrypt text
    # =========================================

    def encrypt_text(
        self,
        message,
        password
    ):

        data = message.encode(
            "utf-8"
        )

        return self.encrypt_bytes(
            data,
            password
        )


    # =========================================
    # Decrypt text
    # =========================================

    def decrypt_text(
        self,
        encrypted_data,
        password
    ):

        data = self.decrypt_bytes(
            encrypted_data,
            password
        )

        return data.decode(
            "utf-8"
        )