# ============================================================================
# TROT SYSTEM v8.0 - LOGGER (OPTIMISÉ)
# ============================================================================

import logging
import sys
import json
import os
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """
    Formatter pour logs JSON structurés.
    
    Permet parsing automatique par outils comme Logstash, CloudWatch, etc.
    """
    
    def format(self, record):
        """Formate un log en JSON."""
        log_data = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Ajout contexte supplémentaire si présent
        if hasattr(record, 'extra') and record.extra:
            log_data.update(record.extra)
        
        # Ajout exception si présente
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_logger(name: str = "trot-system", level: str = "INFO", 
                json_logs: bool = None) -> logging.Logger:
    """
    Configure le logger pour le projet.
    
    Args:
        name: Nom du logger
        level: Niveau de log (DEBUG, INFO, WARNING, ERROR)
        json_logs: Force JSON logs (auto-détecté si None)
    
    Returns:
        Logger configuré
    """
    logger = logging.getLogger(name)
    
    # Éviter duplication handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, level.upper()))
    
    # Détection auto format JSON si production
    if json_logs is None:
        # JSON si en production (FLASK_ENV=production ou LOG_FORMAT=json)
        json_logs = (
            os.getenv('FLASK_ENV') == 'production' or
            os.getenv('LOG_FORMAT', '').lower() == 'json'
        )
    
    # Sélection formatter
    if json_logs:
        formatter = JSONFormatter(datefmt='%Y-%m-%dT%H:%M:%S')
    else:
        # Format texte standard (développement)
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Handler console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Log info format
    if json_logs:
        logger.info("Logger initialisé (format JSON)")
    else:
        logger.info("Logger initialisé (format texte)")
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Récupère un logger existant ou en crée un.
    
    Args:
        name: Nom du logger (None = root logger)
    
    Returns:
        Logger
    """
    if name:
        return logging.getLogger(name)
    return logging.getLogger("trot-system")
