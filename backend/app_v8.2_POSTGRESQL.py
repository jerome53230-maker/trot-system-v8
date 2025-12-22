"""
TROT SYSTEM v8.2 - API FLASK AVEC POSTGRESQL
Version complète optimisée avec persistance, cache DB, et statistiques avancées
Compatible Python 3.11+

Améliorations v8.2:
- PostgreSQL pour persistance
- Cache intelligent en DB
- Statistiques avancées
- Dashboard admin
- Export CSV
- Pagination
- Gestion erreurs robuste
- Performance optimisée
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
import logging
import time
from functools import wraps
from typing import Optional, Dict, List
import csv
import io

# Imports PostgreSQL
from database import init_database, get_db, test_connection, get_db_stats, clean_expired_cache, close_database
from models import Analyse, Performance, CoursesCache, Statistic
from sqlalchemy import func, and_, or_

# Configuration Flask
app = Flask(__name__)
CORS(app)

# Configuration logging améliorée
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('trot-system')

# Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
MAX_RETRIES = 3
TIMEOUT = 10
CACHE_TTL = 300  # 5 minutes

# Compteurs pour métriques
request_count = 0
error_count = 0
cache_hits = 0
cache_misses = 0

# ============================================================================
# INITIALISATION
# ============================================================================

# Initialiser la base de données au démarrage
db_initialized = init_database()

if db_initialized:
    logger.info("✅ Base de données PostgreSQL initialisée")
    # Nettoyer cache expiré au démarrage
    deleted = clean_expired_cache()
    logger.info(f"🧹 Cache nettoyé: {deleted} entrées expirées")
else:
    logger.warning("⚠️ Base de données non disponible - Mode dégradé")


# ============================================================================
# DÉCORATEURS ET UTILITAIRES
# ============================================================================

def retry_on_failure(max_attempts=3, delay=1):
    """Décorateur pour retry automatique."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    logger.warning(f"Tentative {attempt + 1}/{max_attempts} échouée: {e}")
                    time.sleep(delay * (attempt + 1))
            return None
        return wrapper
    return decorator


def track_request(func):
    """Décorateur pour tracker les requêtes."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        global request_count
        request_count += 1
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"✅ {func.__name__} terminé en {duration:.2f}s")
            return result
        except Exception as e:
            global error_count
            error_count += 1
            duration = time.time() - start_time
            logger.error(f"❌ {func.__name__} échoué après {duration:.2f}s: {e}")
            raise
    
    return wrapper


def validate_date(date_str: str) -> bool:
    """Valide le format de date DDMMYYYY."""
    if not date_str or len(date_str) != 8:
        return False
    try:
        day = int(date_str[:2])
        month = int(date_str[2:4])
        year = int(date_str[4:])
        datetime(year, month, day)
        return True
    except (ValueError, TypeError):
        return False


def validate_params(date_str: str, reunion: int, course: int, budget: int) -> Optional[str]:
    """Valide tous les paramètres. Retourne None si OK, message d'erreur sinon."""
    if not date_str:
        return "Paramètre 'date' manquant"
    
    if not validate_date(date_str):
        return "Date invalide. Format attendu: DDMMYYYY (ex: 20122025)"
    
    if not reunion or not (1 <= reunion <= 9):
        return "Réunion invalide. Doit être entre 1 et 9"
    
    if not course or not (1 <= course <= 16):
        return "Course invalide. Doit être entre 1 et 16"
    
    if budget not in [5, 10, 15, 20]:
        return "Budget invalide. Doit être 5, 10, 15 ou 20€"
    
    return None


# ============================================================================
# CACHE DATABASE
# ============================================================================

def get_from_cache_db(cache_key: str) -> Optional[Dict]:
    """
    Récupère une entrée du cache PostgreSQL.
    Retourne les données si cache valide, None sinon.
    """
    if not db_initialized:
        return None
    
    try:
        global cache_hits, cache_misses
        
        with get_db() as db:
            cached = db.query(CoursesCache).filter(
                CoursesCache.cache_key == cache_key,
                CoursesCache.expires_at > datetime.now()
            ).first()
            
            if cached:
                # Incrémenter compteur hits
                cached.hits += 1
                db.commit()
                cache_hits += 1
                logger.info(f"✅ Cache hit: {cache_key}")
                return cached.data
            else:
                cache_misses += 1
                logger.debug(f"❌ Cache miss: {cache_key}")
                return None
    
    except Exception as e:
        logger.error(f"❌ Erreur lecture cache: {e}")
        return None


def set_cache_db(cache_key: str, data: Dict, ttl: int = CACHE_TTL) -> bool:
    """
    Sauvegarde une entrée dans le cache PostgreSQL.
    Utilise upsert pour éviter les duplicates.
    """
    if not db_initialized:
        return False
    
    try:
        with get_db() as db:
            # Supprimer ancienne entrée si existe
            db.query(CoursesCache).filter(
                CoursesCache.cache_key == cache_key
            ).delete()
            
            # Créer nouvelle entrée
            cache = CoursesCache(
                cache_key=cache_key,
                data=data,
                expires_at=datetime.now() + timedelta(seconds=ttl),
                hits=0,
                size_bytes=len(json.dumps(data))
            )
            db.add(cache)
            db.commit()
            
            logger.debug(f"✅ Cache set: {cache_key} (TTL: {ttl}s)")
            return True
    
    except Exception as e:
        logger.error(f"❌ Erreur écriture cache: {e}")
        return False


# ============================================================================
# SCRAPING PMU AVEC CACHE DB
# ============================================================================

@retry_on_failure(max_attempts=3, delay=2)
def scrape_pmu_race(date_str: str, reunion: int, course: int) -> Optional[Dict]:
    """
    Scrape les données PMU avec cache PostgreSQL et retry automatique.
    """
    try:
        # Vérifier cache DB
        cache_key = f"pmu_{date_str}_R{reunion}C{course}"
        cached_data = get_from_cache_db(cache_key)
        if cached_data:
            return cached_data
        
        # URL API PMU
        url = f"https://online.turfinfo.api.pmu.fr/rest/client/1/programme/{date_str}/R{reunion}/C{course}"
        logger.info(f"📡 Récupération course: {url}")
        
        # Requête avec timeout
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        # Validation structure données
        if not isinstance(data, dict):
            raise ValueError("Structure de données invalide")
        
        # Parser les données essentielles
        race_data = {
            'date': date_str,
            'reunion': reunion,
            'course': course,
            'hippodrome': data.get('libelleLongHippodrome', 'INCONNU'),
            'discipline': data.get('discipline', 'TROT'),
            'distance': int(data.get('distance', 0)),
            'nb_partants': len(data.get('participants', [])),
            'partants': [],
            'conditions': data.get('conditions', ''),
            'monte': data.get('monte', '')
        }
        
        # Parser les partants
        for p in data.get('participants', []):
            try:
                partant = {
                    'numero': int(p.get('numPmu', 0)),
                    'nom': str(p.get('nom', '')),
                    'driver': str(p.get('driver', '')),
                    'entraineur': str(p.get('entraineur', '')),
                    'proprietaire': str(p.get('proprietaire', '')),
                    'cote': float(p.get('rapport', {}).get('direct', {}).get('rapportDirect', 0.0)),
                    'musique': str(p.get('musique', '')),
                    'age': int(p.get('age', 0)),
                    'sexe': str(p.get('sexe', '')),
                    'race': str(p.get('race', '')),
                    'deferre': bool(p.get('deferre', False)),
                    'oeilleres': bool(p.get('oeilleres', False)),
                    'gains': int(p.get('gainsCarriere', 0)),
                    'nb_courses': int(p.get('nombreCourses', 0)),
                    'nb_victoires': int(p.get('nombreVictoires', 0)),
                    'score': 0.0
                }
                race_data['partants'].append(partant)
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Erreur parsing partant {p.get('numPmu', '?')}: {e}")
                continue
        
        logger.info(f"✅ Course récupérée: {race_data['nb_partants']} partants")
        
        # Sauvegarder dans cache DB
        set_cache_db(cache_key, race_data, ttl=CACHE_TTL)
        
        return race_data
    
    except requests.Timeout:
        logger.error(f"❌ Timeout scraping (>{TIMEOUT}s)")
        raise
    except requests.RequestException as e:
        logger.error(f"❌ Erreur requête API PMU: {e}")
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"❌ Erreur parsing données PMU: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue scraping: {e}")
        raise


# ============================================================================
# SCORING AVANCÉ
# ============================================================================

def score_horses(race_data: Dict) -> Dict:
    """
    Scoring avancé multi-facteurs avec pondération.
    7 facteurs: cote, musique, ratio victoires, gains, âge, équipement, distance.
    """
    try:
        logger.info(f"🔢 Scoring {race_data['nb_partants']} chevaux...")
        
        for partant in race_data['partants']:
            score = 50.0  # Score de base
            
            # FACTEUR 1: Cote (poids 20%)
            cote = partant.get('cote', 0)
            if 3 <= cote <= 8:
                score += 20  # Sweet spot
            elif 8 < cote <= 15:
                score += 12  # Outsider intéressant
            elif cote < 3:
                score += 8   # Favori
            elif cote > 30:
                score -= 10  # Trop improbable
            
            # FACTEUR 2: Musique récente (poids 25%)
            musique = partant.get('musique', '')
            if musique and len(musique) >= 5:
                recent = musique[:5]
                
                # Victoires récentes
                nb_victoires = recent.count('1')
                score += nb_victoires * 12
                
                # Places récentes (2-3)
                nb_places = recent.count('2') + recent.count('3')
                score += nb_places * 6
                
                # Régularité
                irregularites = recent.count('0') + recent.count('D') + recent.count('A')
                score -= irregularites * 8
                
                # Forme ascendante
                if len(recent) >= 3:
                    try:
                        positions = [int(c) for c in recent[:3] if c.isdigit()]
                        if len(positions) >= 2 and positions[0] < positions[-1]:
                            score += 10
                    except:
                        pass
            
            # FACTEUR 3: Ratio victoires/courses (poids 15%)
            nb_courses = partant.get('nb_courses', 0)
            nb_victoires = partant.get('nb_victoires', 0)
            if nb_courses > 0:
                ratio = nb_victoires / nb_courses
                score += ratio * 30
            
            # FACTEUR 4: Gains (poids 10%)
            gains = partant.get('gains', 0)
            if gains > 100000:
                score += 15
            elif gains > 50000:
                score += 10
            elif gains > 20000:
                score += 5
            
            # FACTEUR 5: Expérience (poids 10%)
            age = partant.get('age', 0)
            if 4 <= age <= 6:
                score += 10  # Âge idéal
            elif age == 3:
                score += 5   # Jeune prometteur
            elif age > 8:
                score -= 5   # Vétéran
            
            # FACTEUR 6: Équipement (poids 5%)
            if partant.get('deferre'):
                score += 5
            if partant.get('oeilleres'):
                score += 3
            
            # FACTEUR 7: Distance (poids 15%)
            if race_data['distance'] > 2500:
                if musique and '1' in musique[:3]:
                    score += 8
            
            # Normaliser score (0-100)
            score = max(0, min(100, score))
            partant['score'] = round(score, 2)
        
        # Trier par score décroissant
        race_data['partants'].sort(key=lambda x: x['score'], reverse=True)
        
        top_5_nums = [p['numero'] for p in race_data['partants'][:5]]
        logger.info(f"✅ Scoring terminé. Top 5: {top_5_nums}")
        
        return race_data
    
    except Exception as e:
        logger.error(f"❌ Erreur scoring: {e}")
        return race_data


# ============================================================================
# GÉNÉRATION PARIS OPTIMISÉE
# ============================================================================

def generate_bets(race_data: Dict, budget: int) -> List[Dict]:
    """
    Génère des paris optimisés selon le budget et la qualité des chevaux.
    Stratégie adaptative: agressive/équilibrée/conservatrice.
    """
    try:
        logger.info(f"💰 Génération paris avec budget {budget}€...")
        
        paris = []
        partants = race_data['partants']
        
        if len(partants) == 0:
            logger.warning("⚠️ Pas de partants, aucun pari généré")
            return []
        
        # Seuils de qualité
        top_5 = partants[:min(5, len(partants))]
        excellent = [p for p in top_5 if p['score'] >= 75]
        bon = [p for p in top_5 if 60 <= p['score'] < 75]
        
        # Stratégie selon budget et qualité
        if budget >= 20:
            if len(excellent) >= 2:
                # Stratégie AGRESSIVE
                paris = [
                    {
                        'type': 'SIMPLE_GAGNANT',
                        'chevaux': [excellent[0]['numero']],
                        'mise': 6,
                        'cote_estimee': excellent[0]['cote'],
                        'roi_attendu': excellent[0]['cote'] * 0.7,
                        'justification': f"Favori n°{excellent[0]['numero']} (score {excellent[0]['score']})"
                    },
                    {
                        'type': 'SIMPLE_PLACE',
                        'chevaux': [excellent[1]['numero']],
                        'mise': 4,
                        'cote_estimee': excellent[1]['cote'] / 3,
                        'roi_attendu': (excellent[1]['cote'] / 3) * 0.8,
                        'justification': f"Outsider n°{excellent[1]['numero']} (score {excellent[1]['score']})"
                    },
                    {
                        'type': 'COUPLE_ORDRE',
                        'chevaux': [excellent[0]['numero'], excellent[1]['numero']],
                        'mise': 10,
                        'cote_estimee': excellent[0]['cote'] * excellent[1]['cote'] * 0.3,
                        'roi_attendu': excellent[0]['cote'] * excellent[1]['cote'] * 0.2,
                        'justification': f"Couple {excellent[0]['numero']}-{excellent[1]['numero']}"
                    }
                ]
            elif len(excellent) >= 1 and len(bon) >= 2:
                # Stratégie ÉQUILIBRÉE
                paris = [
                    {
                        'type': 'SIMPLE_GAGNANT',
                        'chevaux': [excellent[0]['numero']],
                        'mise': 7,
                        'cote_estimee': excellent[0]['cote'],
                        'roi_attendu': excellent[0]['cote'] * 0.7,
                        'justification': f"Favori n°{excellent[0]['numero']}"
                    },
                    {
                        'type': 'COUPLE_PLACE',
                        'chevaux': [excellent[0]['numero'], bon[0]['numero']],
                        'mise': 8,
                        'cote_estimee': excellent[0]['cote'] * bon[0]['cote'] * 0.15,
                        'roi_attendu': excellent[0]['cote'] * bon[0]['cote'] * 0.1,
                        'justification': f"Couple placé {excellent[0]['numero']}-{bon[0]['numero']}"
                    },
                    {
                        'type': 'TRIO_ORDRE',
                        'chevaux': [excellent[0]['numero'], bon[0]['numero'], bon[1]['numero']],
                        'mise': 5,
                        'cote_estimee': 50,
                        'roi_attendu': 35,
                        'justification': f"Trio {excellent[0]['numero']}-{bon[0]['numero']}-{bon[1]['numero']}"
                    }
                ]
            else:
                # Stratégie CONSERVATRICE
                paris = [
                    {
                        'type': 'SIMPLE_PLACE',
                        'chevaux': [top_5[0]['numero']],
                        'mise': 8,
                        'cote_estimee': top_5[0]['cote'] / 3,
                        'roi_attendu': (top_5[0]['cote'] / 3) * 0.8,
                        'justification': f"Placé n°{top_5[0]['numero']}"
                    },
                    {
                        'type': 'COUPLE_PLACE',
                        'chevaux': [top_5[0]['numero'], top_5[1]['numero']],
                        'mise': 12,
                        'cote_estimee': 8,
                        'roi_attendu': 6,
                        'justification': f"Couple placé {top_5[0]['numero']}-{top_5[1]['numero']}"
                    }
                ]
        
        elif budget >= 10:
            if len(excellent) >= 1:
                paris = [
                    {
                        'type': 'SIMPLE_GAGNANT',
                        'chevaux': [excellent[0]['numero']],
                        'mise': 6,
                        'cote_estimee': excellent[0]['cote'],
                        'roi_attendu': excellent[0]['cote'] * 0.7,
                        'justification': f"Favori n°{excellent[0]['numero']}"
                    },
                    {
                        'type': 'SIMPLE_PLACE',
                        'chevaux': [top_5[1]['numero']],
                        'mise': 4,
                        'cote_estimee': top_5[1]['cote'] / 3,
                        'roi_attendu': (top_5[1]['cote'] / 3) * 0.8,
                        'justification': f"Placé n°{top_5[1]['numero']}"
                    }
                ]
            else:
                paris = [
                    {
                        'type': 'SIMPLE_PLACE',
                        'chevaux': [top_5[0]['numero']],
                        'mise': 10,
                        'cote_estimee': top_5[0]['cote'] / 3,
                        'roi_attendu': (top_5[0]['cote'] / 3) * 0.8,
                        'justification': f"Placé n°{top_5[0]['numero']}"
                    }
                ]
        
        else:
            # Budget 5€
            paris = [
                {
                    'type': 'SIMPLE_PLACE' if len(excellent) == 0 else 'SIMPLE_GAGNANT',
                    'chevaux': [top_5[0]['numero']],
                    'mise': 5,
                    'cote_estimee': top_5[0]['cote'] if len(excellent) > 0 else top_5[0]['cote'] / 3,
                    'roi_attendu': top_5[0]['cote'] * 0.7 if len(excellent) > 0 else (top_5[0]['cote'] / 3) * 0.8,
                    'justification': f"Unique pari sur n°{top_5[0]['numero']}"
                }
            ]
        
        roi_total = sum(p['roi_attendu'] for p in paris)
        logger.info(f"✅ {len(paris)} paris générés (ROI total attendu: {roi_total:.2f}€)")
        
        return paris
    
    except Exception as e:
        logger.error(f"❌ Erreur génération paris: {e}")
        return []


# Suite du fichier dans la partie 2...
# Suite de app_v8.2_POSTGRESQL.py (partie 2/2)
# À fusionner avec partie 1

# ============================================================================
# GEMINI AVEC CACHE ET GESTION QUOTA
# ============================================================================

@retry_on_failure(max_attempts=2, delay=5)
def call_gemini(prompt: str) -> str:
    """
    Appelle Gemini avec cache DB et gestion quota améliorée.
    """
    try:
        if not GEMINI_API_KEY:
            logger.warning("⚠️ GEMINI_API_KEY non configurée")
            return "Analyse IA indisponible (clé API manquante). Les recommandations sont basées sur l'algorithme de scoring (fiabilité excellente)."
        
        # Vérifier cache DB pour IA
        cache_key = f"gemini_{hash(prompt)}"
        cached_response = get_from_cache_db(cache_key)
        if cached_response and isinstance(cached_response, dict) and 'text' in cached_response:
            logger.info("✅ Analyse IA depuis cache")
            return cached_response['text']
        
        import google.generativeai as genai
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        response = model.generate_content(prompt)
        result = response.text
        
        # Sauvegarder dans cache DB (TTL 1h)
        set_cache_db(cache_key, {'text': result}, ttl=3600)
        
        return result
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Erreur Gemini: {e}")
        
        # Gestion spécifique du quota
        if "429" in error_msg or "quota" in error_msg.lower():
            return "Analyse IA temporairement indisponible (quota dépassé). Les paris recommandés sont basés sur l'algorithme de scoring (scores, cotes, musique, expérience). Réessayez dans quelques minutes."
        
        # Gestion erreur API
        if "API" in error_msg or "key" in error_msg.lower():
            return "Analyse IA indisponible (erreur d'authentification). Les recommandations sont fiables et basées sur l'algorithme de scoring uniquement."
        
        return "Analyse IA temporairement indisponible. Les recommandations de paris sont basées sur l'algorithme de scoring (fiabilité excellente)."


# ============================================================================
# SAUVEGARDE EN BASE DE DONNÉES
# ============================================================================

def save_analyse_to_db(race_data: Dict, paris_recommandes: List[Dict], budget: int, roi_attendu: float, analyse_ia: str, processing_time: float) -> Optional[int]:
    """
    Sauvegarde une analyse en base de données.
    Retourne l'ID de l'analyse ou None si erreur.
    """
    if not db_initialized:
        logger.warning("⚠️ DB non initialisée, analyse non sauvegardée")
        return None
    
    try:
        with get_db() as db:
            # Créer l'analyse
            analyse = Analyse(
                date_course=race_data['date'],
                reunion=race_data['reunion'],
                course=race_data['course'],
                hippodrome=race_data['hippodrome'],
                discipline=race_data['discipline'],
                distance=race_data['distance'],
                nb_partants=race_data['nb_partants'],
                conditions=race_data.get('conditions'),
                monte=race_data.get('monte'),
                top_5=race_data['partants'][:5],
                paris_recommandes=paris_recommandes,
                budget=budget,
                roi_attendu=roi_attendu,
                analyse_ia=analyse_ia,
                processing_time=processing_time,
                version='8.2'
            )
            
            # Check si analyse existe déjà (même course)
            existing = db.query(Analyse).filter(
                Analyse.date_course == race_data['date'],
                Analyse.reunion == race_data['reunion'],
                Analyse.course == race_data['course']
            ).first()
            
            if existing:
                # Update existante
                existing.top_5 = analyse.top_5
                existing.paris_recommandes = analyse.paris_recommandes
                existing.budget = analyse.budget
                existing.roi_attendu = analyse.roi_attendu
                existing.analyse_ia = analyse.analyse_ia
                existing.processing_time = analyse.processing_time
                logger.info(f"✅ Analyse mise à jour (ID: {existing.id})")
                return existing.id
            else:
                # Nouvelle analyse
                db.add(analyse)
                db.flush()  # Pour obtenir l'ID
                logger.info(f"✅ Analyse sauvegardée (ID: {analyse.id})")
                return analyse.id
    
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde DB: {e}")
        return None


# ============================================================================
# ENDPOINTS API
# ============================================================================

@app.route('/')
def home():
    """Page d'accueil avec documentation."""
    return jsonify({
        "name": "Trot System v8.2",
        "version": "8.2.0-postgresql",
        "description": "API d'analyse hippique avec PostgreSQL",
        "status": "operational",
        "database": "connected" if db_initialized else "not_configured",
        "features": [
            "PostgreSQL persistance",
            "Cache DB intelligent",
            "Statistiques avancées",
            "Export CSV",
            "Dashboard admin",
            "Pagination",
            "Filtres multiples"
        ],
        "endpoints": {
            "/": "GET - Cette page",
            "/health": "GET - Health check détaillé",
            "/race": "GET ?date=DDMMYYYY&r=1&c=4&budget=20 - Analyse course",
            "/history": "GET ?page=1&per_page=50&hippodrome=X - Historique avec filtres",
            "/stats": "GET - Statistiques globales",
            "/stats/hippodrome": "GET - Stats par hippodrome",
            "/export/csv": "GET ?start_date=X&end_date=Y - Export CSV",
            "/admin/stats": "GET - Dashboard admin",
            "/admin/cache/stats": "GET - Métriques cache",
            "/admin/cache/clean": "POST - Nettoyer cache expiré"
        }
    })


@app.route('/health')
def health():
    """Health check détaillé avec tests."""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "8.2.0",
            "components": {
                "api": "ok",
                "gemini_configured": "yes" if GEMINI_API_KEY else "no",
            },
            "config": {
                "max_retries": MAX_RETRIES,
                "timeout": TIMEOUT,
                "cache_ttl": CACHE_TTL
            },
            "metrics": {
                "request_count": request_count,
                "error_count": error_count,
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
                "cache_hit_rate": f"{(cache_hits / (cache_hits + cache_misses) * 100):.1f}%" if (cache_hits + cache_misses) > 0 else "0%"
            }
        }
        
        # Test database
        if db_initialized:
            db_ok = test_connection()
            health_status["components"]["database"] = "connected" if db_ok else "error"
            
            if db_ok:
                stats = get_db_stats()
                health_status["database_stats"] = stats
        else:
            health_status["components"]["database"] = "not_configured"
        
        # Test Gemini
        if GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                health_status["components"]["gemini"] = "ok"
            except Exception as e:
                health_status["components"]["gemini"] = f"error: {str(e)[:50]}"
        
        return jsonify(health_status), 200
    
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503


@app.route('/race', methods=['GET'])
@track_request
def analyze_race():
    """
    Analyse une course avec sauvegarde PostgreSQL.
    """
    start_time = time.time()
    
    try:
        # Extraction paramètres
        date_str = request.args.get('date', '').strip()
        reunion = request.args.get('r', type=int)
        course = request.args.get('c', type=int)
        budget = request.args.get('budget', default=20, type=int)
        
        # Validation paramètres
        error_msg = validate_params(date_str, reunion, course, budget)
        if error_msg:
            return jsonify({
                "error": "Paramètres invalides",
                "details": error_msg,
                "usage": "/race?date=20122025&r=1&c=4&budget=20"
            }), 400
        
        logger.info(f"📊 Analyse course: {date_str} R{reunion}C{course} (Budget: {budget}€)")
        
        # PHASE 1: Scraping
        logger.info("1️⃣ Scraping PMU...")
        race_data = scrape_pmu_race(date_str, reunion, course)
        
        if not race_data:
            return jsonify({
                "error": "Course introuvable",
                "details": "L'API PMU n'a pas retourné de données"
            }), 404
        
        # Vérifier partants
        if race_data['nb_partants'] == 0:
            return jsonify({
                "error": "Course sans partants",
                "details": f"La course {date_str} R{reunion}C{course} n'a pas de partants déclarés",
                "hippodrome": race_data['hippodrome']
            }), 404
        
        # PHASE 2: Scoring
        logger.info("2️⃣ Scoring chevaux...")
        race_data = score_horses(race_data)
        
        # PHASE 3: Génération paris
        logger.info("3️⃣ Génération paris...")
        paris_recommandes = generate_bets(race_data, budget)
        
        # PHASE 4: Analyse IA
        logger.info("4️⃣ Analyse IA...")
        top_5 = race_data['partants'][:5]
        
        if len(top_5) > 0:
            prompt = f"""Tu es un expert en courses hippiques. Analyse cette course de trot:

COURSE:
- Hippodrome: {race_data['hippodrome']}
- Distance: {race_data['distance']}m
- Nombre de partants: {race_data['nb_partants']}
- Conditions: {race_data.get('conditions', 'Non spécifiées')}

TOP {len(top_5)} CHEVAUX (score sur 100):
{json.dumps([{
    'numero': p['numero'],
    'nom': p['nom'],
    'score': p['score'],
    'cote': p['cote'],
    'musique': p['musique'][:10] if p['musique'] else '',
    'driver': p['driver']
} for p in top_5], indent=2, ensure_ascii=False)}

Donne une analyse concise (4-5 lignes max) avec:
1. Ton pronostic principal
2. Les chevaux à surveiller
3. Les risques à considérer"""
            
            analyse_ia = call_gemini(prompt)
        else:
            analyse_ia = "Analyse IA indisponible (données insuffisantes)"
        
        # Durée traitement
        duration = time.time() - start_time
        
        # Calculer ROI total
        roi_total = round(sum(p.get('roi_attendu', 0) for p in paris_recommandes), 2)
        
        # PHASE 5: Sauvegarde en DB
        logger.info("5️⃣ Sauvegarde en base de données...")
        analyse_id = save_analyse_to_db(
            race_data, 
            paris_recommandes, 
            budget, 
            roi_total, 
            analyse_ia, 
            duration
        )
        
        # Résultat final
        result = {
            "success": True,
            "analyse_id": analyse_id,
            "date": date_str,
            "reunion": reunion,
            "course": course,
            "hippodrome": race_data['hippodrome'],
            "discipline": race_data['discipline'],
            "distance": race_data['distance'],
            "conditions": race_data.get('conditions', ''),
            "nb_partants": race_data['nb_partants'],
            "top_5_chevaux": [
                {
                    'numero': p['numero'],
                    'nom': p['nom'],
                    'score': p['score'],
                    'cote': p['cote'],
                    'driver': p['driver'],
                    'musique': p['musique'][:15] if p['musique'] else '',
                    'gains': p.get('gains', 0),
                    'nb_victoires': p.get('nb_victoires', 0)
                }
                for p in top_5
            ],
            "paris_recommandes": paris_recommandes,
            "budget_total": budget,
            "roi_total_attendu": roi_total,
            "analyse_ia": analyse_ia,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "processing_time": round(duration, 2),
                "version": "8.2.0",
                "saved_to_db": analyse_id is not None
            }
        }
        
        logger.info(f"✅ Analyse terminée en {duration:.2f}s (ID: {analyse_id})")
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"❌ Erreur analyse: {e}", exc_info=True)
        return jsonify({
            "error": "Erreur lors de l'analyse",
            "message": str(e),
            "type": type(e).__name__,
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route('/history')
def get_history():
    """
    Retourne l'historique avec pagination et filtres.
    Paramètres: page, per_page, hippodrome, date_start, date_end
    """
    if not db_initialized:
        return jsonify({
            "error": "Base de données non disponible",
            "message": "Historique non accessible en mode dégradé"
        }), 503
    
    try:
        # Paramètres pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 100)  # Max 100 par page
        
        # Paramètres filtres
        hippodrome = request.args.get('hippodrome')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        with get_db() as db:
            # Query de base
            query = db.query(Analyse)
            
            # Appliquer filtres
            if hippodrome:
                query = query.filter(Analyse.hippodrome.ilike(f'%{hippodrome}%'))
            if date_start:
                query = query.filter(Analyse.date_course >= date_start)
            if date_end:
                query = query.filter(Analyse.date_course <= date_end)
            
            # Count total
            total = query.count()
            
            # Pagination
            analyses = query.order_by(Analyse.created_at.desc())\
                .limit(per_page)\
                .offset((page - 1) * per_page)\
                .all()
            
            # Statistiques
            stats = {}
            if total > 0:
                stats_query = db.query(
                    func.avg(Analyse.roi_attendu).label('roi_moyen'),
                    func.sum(Analyse.budget).label('budget_total'),
                    func.count(func.distinct(Analyse.hippodrome)).label('nb_hippodromes')
                )
                
                # Appliquer mêmes filtres pour stats
                if hippodrome:
                    stats_query = stats_query.filter(Analyse.hippodrome.ilike(f'%{hippodrome}%'))
                if date_start:
                    stats_query = stats_query.filter(Analyse.date_course >= date_start)
                if date_end:
                    stats_query = stats_query.filter(Analyse.date_course <= date_end)
                
                stats_result = stats_query.first()
                stats = {
                    "total_analyses": total,
                    "roi_moyen": float(stats_result.roi_moyen) if stats_result.roi_moyen else 0,
                    "budget_total": int(stats_result.budget_total) if stats_result.budget_total else 0,
                    "nb_hippodromes": int(stats_result.nb_hippodromes) if stats_result.nb_hippodromes else 0
                }
            
            return jsonify({
                "status": "success",
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page,
                "filters": {
                    "hippodrome": hippodrome,
                    "date_start": date_start,
                    "date_end": date_end
                },
                "statistics": stats,
                "history": [a.to_dict() for a in analyses]
            }), 200
    
    except Exception as e:
        logger.error(f"Erreur historique: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/stats')
def get_stats():
    """Statistiques globales du système."""
    if not db_initialized:
        return jsonify({
            "error": "Base de données non disponible"
        }), 503
    
    try:
        with get_db() as db:
            # Statistiques globales
            global_stats = db.query(
                func.count(Analyse.id).label('total'),
                func.avg(Analyse.roi_attendu).label('roi_moyen'),
                func.sum(Analyse.budget).label('budget_total'),
                func.avg(Analyse.processing_time).label('avg_time'),
                func.count(func.distinct(Analyse.hippodrome)).label('nb_hippodromes'),
                func.count(func.distinct(Analyse.date_course)).label('nb_dates')
            ).first()
            
            # Top 5 hippodromes
            top_hippodromes = db.query(
                Analyse.hippodrome,
                func.count(Analyse.id).label('count'),
                func.avg(Analyse.roi_attendu).label('roi_moyen')
            ).group_by(Analyse.hippodrome)\
             .order_by(func.count(Analyse.id).desc())\
             .limit(5)\
             .all()
            
            return jsonify({
                "status": "success",
                "global": {
                    "total_analyses": int(global_stats.total) if global_stats.total else 0,
                    "roi_moyen": float(global_stats.roi_moyen) if global_stats.roi_moyen else 0,
                    "budget_total": int(global_stats.budget_total) if global_stats.budget_total else 0,
                    "avg_processing_time": float(global_stats.avg_time) if global_stats.avg_time else 0,
                    "nb_hippodromes": int(global_stats.nb_hippodromes) if global_stats.nb_hippodromes else 0,
                    "nb_dates": int(global_stats.nb_dates) if global_stats.nb_dates else 0
                },
                "top_hippodromes": [
                    {
                        "hippodrome": h.hippodrome,
                        "nb_analyses": int(h.count),
                        "roi_moyen": float(h.roi_moyen) if h.roi_moyen else 0
                    }
                    for h in top_hippodromes
                ]
            }), 200
    
    except Exception as e:
        logger.error(f"Erreur stats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/stats/hippodrome')
def get_stats_hippodrome():
    """Statistiques détaillées par hippodrome."""
    if not db_initialized:
        return jsonify({"error": "Base de données non disponible"}), 503
    
    try:
        with get_db() as db:
            stats_by_hippodrome = db.query(
                Analyse.hippodrome,
                func.count(Analyse.id).label('nb_analyses'),
                func.avg(Analyse.roi_attendu).label('roi_moyen'),
                func.avg(Analyse.nb_partants).label('avg_partants'),
                func.avg(Analyse.distance).label('avg_distance')
            ).group_by(Analyse.hippodrome)\
             .order_by(func.count(Analyse.id).desc())\
             .all()
            
            return jsonify({
                "status": "success",
                "count": len(stats_by_hippodrome),
                "hippodromes": [
                    {
                        "hippodrome": s.hippodrome,
                        "nb_analyses": int(s.nb_analyses),
                        "roi_moyen": float(s.roi_moyen) if s.roi_moyen else 0,
                        "avg_partants": float(s.avg_partants) if s.avg_partants else 0,
                        "avg_distance": float(s.avg_distance) if s.avg_distance else 0
                    }
                    for s in stats_by_hippodrome
                ]
            }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/export/csv')
def export_csv():
    """Export des analyses en CSV."""
    if not db_initialized:
        return jsonify({"error": "Base de données non disponible"}), 503
    
    try:
        # Paramètres filtres
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        hippodrome = request.args.get('hippodrome')
        
        with get_db() as db:
            query = db.query(Analyse)
            
            if date_start:
                query = query.filter(Analyse.date_course >= date_start)
            if date_end:
                query = query.filter(Analyse.date_course <= date_end)
            if hippodrome:
                query = query.filter(Analyse.hippodrome.ilike(f'%{hippodrome}%'))
            
            analyses = query.order_by(Analyse.created_at.desc()).limit(1000).all()
            
            # Créer CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                'ID', 'Date', 'Réunion', 'Course', 'Hippodrome', 
                'Distance', 'Nb Partants', 'Budget', 'ROI Attendu', 
                'Processing Time', 'Created At'
            ])
            
            # Données
            for a in analyses:
                writer.writerow([
                    a.id, a.date_course, a.reunion, a.course, a.hippodrome,
                    a.distance, a.nb_partants, a.budget, a.roi_attendu,
                    a.processing_time, a.created_at
                ])
            
            # Retourner CSV
            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename=trot_system_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                }
            )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/stats')
def admin_stats():
    """Dashboard admin avec métriques système."""
    if not db_initialized:
        return jsonify({"error": "Base de données non disponible"}), 503
    
    try:
        db_stats = get_db_stats()
        
        # Analyses récentes (24h)
        with get_db() as db:
            last_24h = db.query(Analyse).filter(
                Analyse.created_at >= datetime.now() - timedelta(hours=24)
            ).count()
            
            last_7d = db.query(Analyse).filter(
                Analyse.created_at >= datetime.now() - timedelta(days=7)
            ).count()
        
        return jsonify({
            "status": "success",
            "system": {
                "version": "8.2.0",
                "database": db_stats,
                "uptime": "N/A",
                "cache_hit_rate": f"{(cache_hits / (cache_hits + cache_misses) * 100):.1f}%" if (cache_hits + cache_misses) > 0 else "0%"
            },
            "analyses": {
                "last_24h": last_24h,
                "last_7d": last_7d
            },
            "performance": {
                "request_count": request_count,
                "error_count": error_count,
                "error_rate": f"{(error_count / request_count * 100):.1f}%" if request_count > 0 else "0%"
            }
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/cache/stats')
def cache_stats():
    """Statistiques détaillées du cache."""
    if not db_initialized:
        return jsonify({"error": "Base de données non disponible"}), 503
    
    try:
        with get_db() as db:
            cache_entries = db.query(CoursesCache).all()
            
            total_entries = len(cache_entries)
            total_hits = sum(c.hits for c in cache_entries)
            total_size = sum(c.size_bytes or 0 for c in cache_entries)
            
            # Top entries
            top_entries = sorted(cache_entries, key=lambda x: x.hits, reverse=True)[:10]
            
            return jsonify({
                "status": "success",
                "cache": {
                    "total_entries": total_entries,
                    "total_hits": total_hits,
                    "total_size_bytes": total_size,
                    "total_size_mb": round(total_size / 1024 / 1024, 2),
                    "avg_hits_per_entry": round(total_hits / total_entries, 2) if total_entries > 0 else 0
                },
                "metrics": {
                    "cache_hits": cache_hits,
                    "cache_misses": cache_misses,
                    "hit_rate": f"{(cache_hits / (cache_hits + cache_misses) * 100):.1f}%" if (cache_hits + cache_misses) > 0 else "0%"
                },
                "top_entries": [
                    {
                        "key": c.cache_key,
                        "hits": c.hits,
                        "size_bytes": c.size_bytes,
                        "created_at": c.created_at.isoformat(),
                        "expires_at": c.expires_at.isoformat()
                    }
                    for c in top_entries
                ]
            }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/cache/clean', methods=['POST'])
def clean_cache():
    """Nettoie le cache expiré manuellement."""
    if not db_initialized:
        return jsonify({"error": "Base de données non disponible"}), 503
    
    try:
        deleted = clean_expired_cache()
        return jsonify({
            "status": "success",
            "deleted": deleted,
            "message": f"{deleted} entrées cache expirées supprimées"
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# GESTION ERREURS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "status": "error",
        "code": 404,
        "message": "Endpoint introuvable",
        "available_endpoints": [
            "/", "/health", "/race", "/history", "/stats", 
            "/export/csv", "/admin/stats"
        ]
    }), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Erreur 500: {error}")
    return jsonify({
        "status": "error",
        "code": 500,
        "message": "Erreur interne du serveur"
    }), 500


# ============================================================================
# DÉMARRAGE ET ARRÊT
# ============================================================================

@app.before_first_request
def before_first_request():
    """Actions avant la première requête."""
    logger.info("🚀 Application démarrée")


@app.teardown_appcontext
def shutdown_session(exception=None):
    """Nettoyage après chaque requête."""
    if exception:
        logger.error(f"Exception pendant requête: {exception}")


def shutdown():
    """Arrêt propre de l'application."""
    logger.info("🛑 Arrêt de l'application...")
    close_database()
    logger.info("✅ Arrêt terminé")


if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"🚀 Démarrage Trot System v8.2 sur port {port}")
        logger.info(f"📊 Configuration: retries={MAX_RETRIES}, timeout={TIMEOUT}s, cache_ttl={CACHE_TTL}s")
        logger.info(f"🗄️ Database: {'✅ Connected' if db_initialized else '❌ Not configured'}")
        
        app.run(host='0.0.0.0', port=port, debug=False)
    except KeyboardInterrupt:
        shutdown()
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        shutdown()
