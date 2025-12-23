import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

# Get key from environment
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

def get_fernet():
    if not ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not found in .env file.")
    return Fernet(ENCRYPTION_KEY.encode())

def encrypt_password(password: str) -> str:
    """Encrypts a plain text password to a base64 string."""
    if not password:
        return None
    f = get_fernet()
    return f.encrypt(password.encode()).decode()

def decrypt_password(encrypted_password: str) -> str:
    """Decrypts a base64 encrypted string to plain text."""
    if not encrypted_password:
        return None
    f = get_fernet()
    try:
        return f.decrypt(encrypted_password.encode()).decode()
    except Exception:
        # If it's already plain text or corrupted, returning as is (for migration safety)
        # However, for production we should probably log an error
        return encrypted_password
