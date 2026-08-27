from crypto import encrypt_message, decrypt_message


# --------------------------------
# Original message
# --------------------------------

message = "HELLO"

password = "mypassword123"


# --------------------------------
# Encrypt
# --------------------------------

encrypted = encrypt_message(
    message,
    password
)

print("Original message:")
print(message)

print("\nEncrypted bytes:")
print(encrypted)

print("\nEncrypted length:")
print(len(encrypted))


# --------------------------------
# Decrypt
# --------------------------------

decrypted = decrypt_message(
    encrypted,
    password
)

print("\nDecrypted message:")
print(decrypted)