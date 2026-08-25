import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Configuración base de la aplicación."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-wiki-mdw-2026-secure")
    
    # Base de datos SQLite
    DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "wiki_mdw.db"))
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
    
    # Paginación por defecto
    ITEMS_PER_PAGE = int(os.getenv("ITEMS_PER_PAGE", 15))
    
    # Parámetros de la aplicación
    APP_NAME = "Wiki-MDW"
    APP_VERSION = "1.0.0"
    APP_DESCRIPTION = "Portal de Inventario, Corta-Palos y Bitácora para Middleware & Sysadmins"


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY")  # Debe definirse obligatoriamente en prod


class TestingConfig(Config):
    TESTING = True
    DATABASE_PATH = ":memory:"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig
}
