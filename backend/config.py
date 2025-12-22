"""
Configuration centralisée - Trot System v8.3 FINAL
Toutes les configurations en un seul endroit
"""

import os
from pathlib import Path

# Répertoire base
BASE_DIR = Path(__file__).parent

# Environnement
ENV = os.getenv('ENVIRONMENT', 'production')
DEBUG = ENV == 'development'

# Flask
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-prod')
PORT = int(os.getenv('PORT', 5000))

# Base de données
DATABASE_URL = os.getenv('DATABASE_URL', '')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Pool connexions
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', 5))
DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', 10))
DB_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', 3600))

# API externe
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
PMU_API_BASE_URL = 'https://online.turfinfo.api.pmu.fr/rest/client/1'

# Retry & Timeout
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', 2))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 10))

# Cache
CACHE_TTL_PMU = int(os.getenv('CACHE_TTL_PMU', 300))  # 5 min
CACHE_TTL_GEMINI = int(os.getenv('CACHE_TTL_GEMINI', 3600))  # 1h
CACHE_MAX_SIZE = int(os.getenv('CACHE_MAX_SIZE', 1000))

# ML
ML_MODEL_DIR = BASE_DIR / 'models'
ML_MODEL_DIR.mkdir(exist_ok=True)
ML_MIN_RACES_TRAINING = int(os.getenv('ML_MIN_RACES_TRAINING', 100))
ML_BATCH_SIZE = int(os.getenv('ML_BATCH_SIZE', 32))

# Pagination
DEFAULT_PAGE_SIZE = int(os.getenv('DEFAULT_PAGE_SIZE', 50))
MAX_PAGE_SIZE = int(os.getenv('MAX_PAGE_SIZE', 100))

# Rate limiting
RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
RATE_LIMIT_PER_HOUR = int(os.getenv('RATE_LIMIT_PER_HOUR', 100))

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO' if ENV == 'production' else 'DEBUG')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# CORS
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')

# Sécurité
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

# Validation
VALID_BUDGETS = [5, 10, 15, 20]
VALID_REUNIONS = range(1, 10)
VALID_COURSES = range(1, 17)


class Config:
    """Classe configuration pour accès facile."""
    
    # Flask
    SECRET_KEY = SECRET_KEY
    DEBUG = DEBUG
    PORT = PORT
    
    # Database
    DATABASE_URL = DATABASE_URL
    DB_POOL_SIZE = DB_POOL_SIZE
    DB_MAX_OVERFLOW = DB_MAX_OVERFLOW
    DB_POOL_RECYCLE = DB_POOL_RECYCLE
    
    # APIs
    GEMINI_API_KEY = GEMINI_API_KEY
    PMU_API_BASE_URL = PMU_API_BASE_URL
    
    # Retry
    MAX_RETRIES = MAX_RETRIES
    RETRY_DELAY = RETRY_DELAY
    REQUEST_TIMEOUT = REQUEST_TIMEOUT
    
    # Cache
    CACHE_TTL_PMU = CACHE_TTL_PMU
    CACHE_TTL_GEMINI = CACHE_TTL_GEMINI
    CACHE_MAX_SIZE = CACHE_MAX_SIZE
    
    # ML
    ML_MODEL_DIR = ML_MODEL_DIR
    ML_MIN_RACES_TRAINING = ML_MIN_RACES_TRAINING
    ML_BATCH_SIZE = ML_BATCH_SIZE
    
    # Pagination
    DEFAULT_PAGE_SIZE = DEFAULT_PAGE_SIZE
    MAX_PAGE_SIZE = MAX_PAGE_SIZE
    
    # Rate limiting
    RATE_LIMIT_ENABLED = RATE_LIMIT_ENABLED
    RATE_LIMIT_PER_HOUR = RATE_LIMIT_PER_HOUR
    
    # Logging
    LOG_LEVEL = LOG_LEVEL
    LOG_FORMAT = LOG_FORMAT
    
    # CORS
    CORS_ORIGINS = CORS_ORIGINS
    
    # Security
    ALLOWED_HOSTS = ALLOWED_HOSTS
    
    # Validation
    VALID_BUDGETS = VALID_BUDGETS
    VALID_REUNIONS = VALID_REUNIONS
    VALID_COURSES = VALID_COURSES
    
    @classmethod
    def validate(cls):
        """Valide la configuration au démarrage."""
        errors = []
        
        if not cls.DATABASE_URL and ENV == 'production':
            errors.append("DATABASE_URL manquante en production")
        
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY manquante (analyse IA désactivée)")
        
        if errors:
            for error in errors:
                print(f"⚠️ Config: {error}")
        
        return len(errors) == 0
    
    @classmethod
    def display(cls):
        """Affiche configuration (sans secrets)."""
        print("=" * 60)
        print("CONFIGURATION TROT SYSTEM v8.3")
        print("=" * 60)
        print(f"Environment: {ENV}")
        print(f"Debug: {cls.DEBUG}")
        print(f"Port: {cls.PORT}")
        print(f"Database: {'✅ Configurée' if cls.DATABASE_URL else '❌ Non configurée'}")
        print(f"Gemini: {'✅ Configurée' if cls.GEMINI_API_KEY else '❌ Non configurée'}")
        print(f"Cache TTL: PMU={cls.CACHE_TTL_PMU}s, Gemini={cls.CACHE_TTL_GEMINI}s")
        print(f"ML Model Dir: {cls.ML_MODEL_DIR}")
        print(f"Rate Limiting: {'✅ Activé' if cls.RATE_LIMIT_ENABLED else '❌ Désactivé'}")
        print("=" * 60)


# Validation au chargement
if __name__ == '__main__':
    Config.validate()
    Config.display()
