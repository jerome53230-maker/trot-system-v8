"""
Database Module - PostgreSQL avec toutes optimisations
Trot System v8.3 FINAL
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from datetime import datetime
import logging

from config import Config

logger = logging.getLogger('trot-system.database')

# Base pour modèles
Base = declarative_base()

# Engine et Session
engine = None
SessionLocal = None


def init_database():
    """
    Initialise connexion PostgreSQL avec pool optimisé.
    
    Returns:
        bool: True si succès, False sinon
    """
    global engine, SessionLocal
    
    try:
        if not Config.DATABASE_URL:
            logger.warning("⚠️ DATABASE_URL non configurée - Mode sans DB")
            return False
        
        # Créer engine avec pool optimisé
        engine = create_engine(
            Config.DATABASE_URL,
            poolclass=QueuePool,
            pool_size=Config.DB_POOL_SIZE,
            max_overflow=Config.DB_MAX_OVERFLOW,
            pool_pre_ping=True,  # Test connexion avant utilisation
            pool_recycle=Config.DB_POOL_RECYCLE,  # Recycle après 1h
            echo=False,  # Pas de logs SQL (performance)
            connect_args={
                'connect_timeout': 10,
                'application_name': 'trot-system'
            }
        )
        
        # Tester connexion
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        
        # Créer session factory
        SessionLocal = scoped_session(
            sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine
            )
        )
        
        logger.info("✅ Connexion PostgreSQL établie")
        return True
    
    except Exception as e:
        logger.error(f"❌ Erreur init database: {e}")
        return False


@contextmanager
def get_db():
    """
    Context manager pour sessions DB avec gestion automatique.
    
    Usage:
        with get_db() as db:
            db.query(Model).all()
    """
    if not SessionLocal:
        raise RuntimeError("Database non initialisée. Appelez init_database() d'abord.")
    
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur DB transaction: {e}")
        raise
    finally:
        db.close()


def test_connection() -> bool:
    """
    Teste si connexion DB fonctionne.
    
    Returns:
        bool: True si OK, False sinon
    """
    if not engine:
        return False
    
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            return result.fetchone()[0] == 1
    except Exception as e:
        logger.error(f"❌ Test connexion échoué: {e}")
        return False


def get_db_stats() -> dict:
    """
    Retourne statistiques database.
    
    Returns:
        dict: Stats (tables, rows, size)
    """
    if not engine:
        return {}
    
    try:
        with get_db() as db:
            # Importer ici pour éviter circular import
            from models import Analyse, Performance, CoursesCache, Statistic
            
            stats = {
                'analyses': db.query(Analyse).count(),
                'performances': db.query(Performance).count(),
                'cache': db.query(CoursesCache).count(),
                'statistics': db.query(Statistic).count()
            }
            
            # Taille DB (PostgreSQL)
            try:
                result = db.execute(
                    "SELECT pg_size_pretty(pg_database_size(current_database()))"
                )
                stats['database_size'] = result.scalar()
            except:
                stats['database_size'] = 'N/A'
            
            return stats
    
    except Exception as e:
        logger.error(f"❌ Erreur get_db_stats: {e}")
        return {}


def clean_expired_cache(batch_size: int = 100) -> int:
    """
    Nettoie cache expiré par batch (optimisé).
    
    Args:
        batch_size: Taille des batchs de suppression
        
    Returns:
        int: Nombre d'entrées supprimées
    """
    if not engine:
        return 0
    
    try:
        from models import CoursesCache
        
        total_deleted = 0
        
        with get_db() as db:
            while True:
                # Supprimer par batch (évite lock table)
                deleted = db.query(CoursesCache).filter(
                    CoursesCache.expires_at < datetime.now()
                ).limit(batch_size).delete(synchronize_session=False)
                
                db.commit()
                total_deleted += deleted
                
                if deleted < batch_size:
                    break
        
        if total_deleted > 0:
            logger.info(f"🧹 Cache nettoyé: {total_deleted} entrées expirées")
        
        return total_deleted
    
    except Exception as e:
        logger.error(f"❌ Erreur clean_expired_cache: {e}")
        return 0


def vacuum_database():
    """
    Lance VACUUM sur database (maintenance PostgreSQL).
    """
    if not engine:
        return
    
    try:
        # VACUUM nécessite autocommit
        connection = engine.raw_connection()
        connection.set_isolation_level(0)  # Autocommit
        cursor = connection.cursor()
        cursor.execute("VACUUM ANALYZE")
        connection.close()
        
        logger.info("✅ VACUUM database terminé")
    
    except Exception as e:
        logger.error(f"❌ Erreur VACUUM: {e}")


def close_database():
    """
    Ferme proprement connexions database.
    """
    global engine, SessionLocal
    
    try:
        if SessionLocal:
            SessionLocal.remove()
        
        if engine:
            engine.dispose()
        
        logger.info("✅ Connexions database fermées")
    
    except Exception as e:
        logger.error(f"❌ Erreur fermeture database: {e}")


def create_tables():
    """
    Crée toutes les tables (pour développement).
    En production, utiliser Alembic migrations.
    """
    if not engine:
        logger.error("❌ Engine non initialisé")
        return False
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tables créées")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur création tables: {e}")
        return False


# Fonctions utilitaires

def execute_raw_sql(sql: str, params: dict = None):
    """
    Exécute SQL brut (à utiliser avec précaution).
    
    Args:
        sql: Requête SQL
        params: Paramètres (sécurisé)
    """
    if not engine:
        raise RuntimeError("Database non initialisée")
    
    with engine.connect() as conn:
        if params:
            result = conn.execute(sql, params)
        else:
            result = conn.execute(sql)
        return result


def get_table_row_counts() -> dict:
    """
    Retourne nombre de lignes par table.
    """
    if not engine:
        return {}
    
    try:
        tables = ['analyses', 'performances', 'courses_cache', 'statistics']
        counts = {}
        
        with engine.connect() as conn:
            for table in tables:
                result = conn.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = result.scalar()
        
        return counts
    
    except Exception as e:
        logger.error(f"❌ Erreur get_table_row_counts: {e}")
        return {}


# Monitoring

class DatabaseMetrics:
    """Classe pour métriques database."""
    
    def __init__(self):
        self.query_count = 0
        self.total_query_time = 0.0
    
    def record_query(self, duration: float):
        """Enregistre durée query."""
        self.query_count += 1
        self.total_query_time += duration
    
    def get_avg_query_time(self) -> float:
        """Retourne temps moyen query."""
        if self.query_count == 0:
            return 0.0
        return self.total_query_time / self.query_count
    
    def reset(self):
        """Reset métriques."""
        self.query_count = 0
        self.total_query_time = 0.0


# Instance globale métriques
db_metrics = DatabaseMetrics()


if __name__ == '__main__':
    # Test connexion
    logging.basicConfig(level=logging.INFO)
    
    if init_database():
        print("✅ Test connexion OK")
        print(f"Stats: {get_db_stats()}")
        close_database()
    else:
        print("❌ Test connexion échoué")
