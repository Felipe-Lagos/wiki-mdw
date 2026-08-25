"""
Servicio de Cifrado Simétrico (Fernet) para proteger credenciales de acceso a servidores.
La clave de cifrado se genera y persiste automáticamente en el archivo .encryption_key
ubicado fuera del control de versiones (añadir al .gitignore).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
KEY_FILE = BASE_DIR / ".encryption_key"


def _get_or_create_key() -> bytes:
    """Obtiene la clave de cifrado Fernet desde disco o la genera si no existe."""
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes().strip()
    
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    KEY_FILE.chmod(0o600)  # Solo lectura del propietario
    return key


def encrypt(plain_text: str) -> str:
    """Cifra un texto plano y retorna la cadena cifrada en base64."""
    if not plain_text:
        return ""
    from cryptography.fernet import Fernet
    key = _get_or_create_key()
    f = Fernet(key)
    return f.encrypt(plain_text.encode()).decode()


def decrypt(cipher_text: str) -> str:
    """Descifra una cadena cifrada con Fernet y retorna el texto original."""
    if not cipher_text:
        return ""
    from cryptography.fernet import Fernet
    try:
        key = _get_or_create_key()
        f = Fernet(key)
        return f.decrypt(cipher_text.encode()).decode()
    except Exception:
        return "⚠️ Error al descifrar — clave de cifrado no coincide"
