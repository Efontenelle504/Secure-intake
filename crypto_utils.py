import os
import json
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

# Development-only persistent key - this will be replaced when ENCRYPTION_KEY secret is set
_DEV_KEY = "8YrVBKhKVgk8_0z-kFVEY_Ny7K8p5L6mQr8e5oTx3l8="
_cached_fernet = None

def get_fernet():
    """
    Get a configured Fernet instance from environment variable.
    Falls back to a persistent development key to avoid decryption errors.
    """
    global _cached_fernet
    
    if _cached_fernet is not None:
        return _cached_fernet
    
    encryption_key = os.environ.get('ENCRYPTION_KEY')
    
    if not encryption_key:
        # For development: Use a persistent key to avoid decryption errors
        logger.warning("ENCRYPTION_KEY not found. Using persistent development key.")
        logger.warning("Add ENCRYPTION_KEY as a Replit secret for production use.")
        try:
            _cached_fernet = Fernet(_DEV_KEY.encode())
            return _cached_fernet
        except Exception as e:
            logger.error(f"Failed to use development key: {e}")
            # Generate a new temporary key as last resort
            temp_key = Fernet.generate_key()
            _cached_fernet = Fernet(temp_key)
            return _cached_fernet
    
    try:
        # Validate the key by attempting to create Fernet instance
        _cached_fernet = Fernet(encryption_key.encode())
        logger.info("Using ENCRYPTION_KEY from environment")
        return _cached_fernet
    except Exception as e:
        raise ValueError(
            f"Invalid ENCRYPTION_KEY: {e}. "
            "Generate a new one with: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
        )

def encrypt_dict(data_dict):
    """
    Encrypt a dictionary to bytes using Fernet.
    
    Args:
        data_dict (dict): Dictionary to encrypt
        
    Returns:
        bytes: Encrypted data
    """
    try:
        fernet = get_fernet()
        json_str = json.dumps(data_dict, sort_keys=True)
        json_bytes = json_str.encode('utf-8')
        encrypted_bytes = fernet.encrypt(json_bytes)
        return encrypted_bytes
    except Exception as e:
        logger.error(f"Error encrypting data: {e}")
        raise

def decrypt_dict(encrypted_bytes):
    """
    Decrypt bytes back to a dictionary using Fernet.
    
    Args:
        encrypted_bytes (bytes): Encrypted data to decrypt
        
    Returns:
        dict: Decrypted dictionary
    """
    try:
        fernet = get_fernet()
        decrypted_bytes = fernet.decrypt(encrypted_bytes)
        json_str = decrypted_bytes.decode('utf-8')
        data_dict = json.loads(json_str)
        return data_dict
    except Exception as e:
        logger.error(f"Error decrypting data: {e}")
        raise
