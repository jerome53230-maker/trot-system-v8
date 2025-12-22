"""
Models - Modèles SQLAlchemy pour PostgreSQL
Trot System v8.2
"""

from sqlalchemy import Column, Integer, String, Text, DECIMAL, TIMESTAMP, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Analyse(Base):
    """
    Modèle pour la table analyses.
    Stocke toutes les analyses de courses effectuées.
    """
    __tablename__ = 'analyses'
    
    # Identifiant
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identifiants course
    date_course = Column(String(8), nullable=False)
    reunion = Column(Integer, nullable=False)
    course = Column(Integer, nullable=False)
    
    # Informations course
    hippodrome = Column(String(100))
    discipline = Column(String(20))
    distance = Column(Integer)
    nb_partants = Column(Integer)
    conditions = Column(Text)
    monte = Column(String(50))
    
    # Résultats analyse (JSON)
    top_5 = Column(JSON)
    paris_recommandes = Column(JSON)
    budget = Column(Integer)
    roi_attendu = Column(DECIMAL(10, 2))
    
    # Analyse IA
    analyse_ia = Column(Text)
    
    # Métadonnées
    processing_time = Column(DECIMAL(10, 2))
    version = Column(String(10), default='8.2')
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    def __repr__(self):
        return f"<Analyse {self.date_course} R{self.reunion}C{self.course}>"
    
    def to_dict(self):
        """Convertit l'objet en dictionnaire."""
        return {
            'id': self.id,
            'date_course': self.date_course,
            'reunion': self.reunion,
            'course': self.course,
            'hippodrome': self.hippodrome,
            'discipline': self.discipline,
            'distance': self.distance,
            'nb_partants': self.nb_partants,
            'top_5': self.top_5,
            'paris_recommandes': self.paris_recommandes,
            'budget': self.budget,
            'roi_attendu': float(self.roi_attendu) if self.roi_attendu else None,
            'analyse_ia': self.analyse_ia,
            'processing_time': float(self.processing_time) if self.processing_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Performance(Base):
    """
    Modèle pour la table performances.
    Stocke les résultats réels des courses (backtesting).
    """
    __tablename__ = 'performances'
    
    # Identifiant
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Lien vers analyse
    analyse_id = Column(Integer, ForeignKey('analyses.id', ondelete='CASCADE'), unique=True)
    
    # Résultat réel (JSON)
    resultat_reel = Column(JSON)
    
    # Performance paris (JSON)
    paris_gagnants = Column(JSON)
    roi_reel = Column(DECIMAL(10, 2))
    gains_reels = Column(DECIMAL(10, 2))
    
    # Précision analyse
    top_5_accuracy = Column(DECIMAL(5, 2))
    
    # Métadonnées
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    def __repr__(self):
        return f"<Performance analyse_id={self.analyse_id} ROI={self.roi_reel}>"
    
    def to_dict(self):
        """Convertit l'objet en dictionnaire."""
        return {
            'id': self.id,
            'analyse_id': self.analyse_id,
            'resultat_reel': self.resultat_reel,
            'paris_gagnants': self.paris_gagnants,
            'roi_reel': float(self.roi_reel) if self.roi_reel else None,
            'gains_reels': float(self.gains_reels) if self.gains_reels else None,
            'top_5_accuracy': float(self.top_5_accuracy) if self.top_5_accuracy else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class CoursesCache(Base):
    """
    Modèle pour la table courses_cache.
    Cache des données PMU pour optimisation.
    """
    __tablename__ = 'courses_cache'
    
    # Identifiant
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Clé de cache
    cache_key = Column(String(100), unique=True, nullable=False)
    
    # Données (JSON)
    data = Column(JSON, nullable=False)
    
    # Expiration
    expires_at = Column(TIMESTAMP, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Métadonnées
    hits = Column(Integer, default=0)
    size_bytes = Column(Integer)
    
    def __repr__(self):
        return f"<Cache {self.cache_key}>"
    
    def to_dict(self):
        """Convertit l'objet en dictionnaire."""
        return {
            'id': self.id,
            'cache_key': self.cache_key,
            'data': self.data,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'hits': self.hits,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Statistic(Base):
    """
    Modèle pour la table statistics.
    Statistiques agrégées du système.
    """
    __tablename__ = 'statistics'
    
    # Identifiant
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Métrique
    metric_name = Column(String(50), nullable=False)
    metric_value = Column(DECIMAL(15, 2), nullable=False)
    metric_unit = Column(String(20))
    
    # Période
    period = Column(String(20))
    period_start = Column(TIMESTAMP)
    period_end = Column(TIMESTAMP)
    
    # Métadonnées
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    def __repr__(self):
        return f"<Stat {self.metric_name}={self.metric_value}>"
    
    def to_dict(self):
        """Convertit l'objet en dictionnaire."""
        return {
            'id': self.id,
            'metric_name': self.metric_name,
            'metric_value': float(self.metric_value) if self.metric_value else None,
            'metric_unit': self.metric_unit,
            'period': self.period,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# Fonction helper pour créer toutes les tables
def create_all_tables(engine):
    """
    Crée toutes les tables dans la base de données.
    À utiliser pour initialisation ou migration.
    """
    Base.metadata.create_all(bind=engine)
