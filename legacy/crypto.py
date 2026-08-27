import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


# --------------------------------
# Generate encryption key
# --------------------------------

def generate_key(password, salt):

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600000
    )

    key = kdf.derive(password.encode("utf-8"))

    return key


# --------------------------------
# Encrypt message
# --------------------------------

def encrypt_message(message, password):

    # Random salt
    salt = os.urandom(16)

    # Generate AES key
    key = generate_key(password, salt)

    # AES-GCM
    aes = AESGCM(key)

    # Random nonce
    nonce = os.urandom(12)

    # Convert message to bytes
    message_bytes = message.encode("utf-8")

    # Encrypt
    ciphertext = aes.encrypt(
        nonce,
        message_bytes,
        None
    )

    # Return everything needed for decryption
    return salt + nonce + ciphertext


# --------------------------------
# Decrypt message
# --------------------------------

def decrypt_message(encrypted_data, password):

    # Extract salt
    salt = encrypted_data[:16]

    # Extract nonce
    nonce = encrypted_data[16:28]

    # Extract ciphertext
    ciphertext = encrypted_data[28:]

    # Generate same AES key
    key = generate_key(password, salt)

    # AES-GCM
    aes = AESGCM(key)

    # Decrypt
    plaintext = aes.decrypt(
        nonce,
        ciphertext,
        None
    )

    # Convert bytes → string
    return plaintext.decode("utf-8")