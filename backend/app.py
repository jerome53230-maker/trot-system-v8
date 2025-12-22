"""
Trot System v8.3 FINAL - Backend API Complet
Toutes corrections appliquées : Flask 3.0, Python 3.11+, Optimisations
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import os
import re
import time
import json

# Configuration
try:
    from config import Config
    config = Config
except ImportError:
    # Fallback si config.py n'existe pas
    class Config:
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
        DATABASE_URL = os.getenv('DATABASE_URL', '')
        MAX_RETRIES = 3
        REQUEST_TIMEOUT = 10
        CACHE_TTL_PMU = 300
        CACHE_TTL_GEMINI = 3600

    config = Config

# Database
DATABASE_URL = config.DATABASE_URL
if DATABASE_URL:
    try:
        from database import init_database, get_db, test_connection, get_db_stats, clean_expired_cache, close_database
        from models import Analyse, Performance, CoursesCache, Statistic
        HAS_DATABASE = True
    except ImportError:
        HAS_DATABASE = False
        logging.warning("⚠️ Modules database non disponibles")
else:
    HAS_DATABASE = False

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('trot-system')

# Flask App
app = Flask(__name__)
CORS(app)

# Gemini AI
GEMINI_API_KEY = config.GEMINI_API_KEY
GEMINI_MODEL = 'gemini-2.0-flash-exp'

# Cache en mémoire
cache_courses = {}
cache_gemini = {}

# Configuration
MAX_RETRIES = config.MAX_RETRIES
RETRY_DELAY = 2
BASE_URL = "https://online.turfinfo.api.pmu.fr/rest/client/1"


# ============================================================================
# UTILITAIRES
# ============================================================================

def clean_cache():
    """Nettoie cache mémoire expiré."""
    global cache_courses, cache_gemini
    now = datetime.now()
    
    # Nettoyer cache courses
    expired_keys = [k for k, v in cache_courses.items() if v.get('expires_at', now) < now]
    for key in expired_keys:
        del cache_courses[key]
    
    # Nettoyer cache Gemini
    expired_keys = [k for k, v in cache_gemini.items() if v.get('expires_at', now) < now]
    for key in expired_keys:
        del cache_gemini[key]
    
    if expired_keys:
        logger.info(f"🧹 Cache nettoyé: {len(expired_keys)} entrées")


def validate_date(date_str: str) -> bool:
    """Valide format date DDMMYYYY."""
    if not date_str or not isinstance(date_str, str):
        return False
    
    if not re.match(r'^\d{8}$', date_str):
        return False
    
    try:
        datetime.strptime(date_str, '%d%m%Y')
        return True
    except ValueError:
        return False


def validate_params(date_str: str, reunion: int, course: int, budget: int) -> Tuple[bool, Optional[str]]:
    """Valide tous les paramètres."""
    # Date
    if not validate_date(date_str):
        return False, "Date invalide. Format requis: DDMMYYYY"
    
    # Réunion
    if not isinstance(reunion, int) or reunion < 1 or reunion > 9:
        return False, "Réunion invalide. Valeur entre 1 et 9"
    
    # Course
    if not isinstance(course, int) or course < 1 or course > 16:
        return False, "Course invalide. Valeur entre 1 et 16"
    
    # Budget
    valid_budgets = [5, 10, 15, 20]
    if budget not in valid_budgets:
        return False, f"Budget invalide. Valeurs acceptées: {valid_budgets}"
    
    return True, None


# ============================================================================
# SCRAPING PMU
# ============================================================================

def scrape_pmu_with_retry(date_str: str, reunion: int, course: int) -> Optional[Dict]:
    """
    Scrape API PMU avec retry automatique.
    
    Args:
        date_str: Date format DDMMYYYY
        reunion: Numéro réunion (1-9)
        course: Numéro course (1-16)
        
    Returns:
        Données course ou None si échec
    """
    # Vérifier cache mémoire
    cache_key = f"{date_str}_R{reunion}_C{course}"
    
    if cache_key in cache_courses:
        cached = cache_courses[cache_key]
        if cached.get('expires_at', datetime.now()) > datetime.now():
            logger.info(f"📦 Cache hit: {cache_key}")
            return cached['data']
    
    # Scraper avec retry
    for attempt in range(MAX_RETRIES):
        try:
            url = f"{BASE_URL}/programme/{date_str}/R{reunion}/C{course}"
            
            logger.info(f"🌐 Scraping PMU (tentative {attempt + 1}/{MAX_RETRIES}): {url}")
            
            response = requests.get(url, timeout=config.REQUEST_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                
                # Valider données
                if not data or 'programme' not in data:
                    logger.warning(f"⚠️ Données invalides: {url}")
                    return None
                
                # Mettre en cache
                cache_courses[cache_key] = {
                    'data': data,
                    'expires_at': datetime.now() + timedelta(seconds=config.CACHE_TTL_PMU)
                }
                
                logger.info(f"✅ Scraping réussi: {cache_key}")
                return data
            
            elif response.status_code == 404:
                logger.warning(f"⚠️ Course introuvable (404): {url}")
                return None
            
            else:
                logger.warning(f"⚠️ Status {response.status_code}: {url}")
        
        except requests.Timeout:
            logger.warning(f"⏱️ Timeout tentative {attempt + 1}/{MAX_RETRIES}")
        
        except Exception as e:
            logger.error(f"❌ Erreur scraping: {e}")
        
        # Retry delay
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
    
    logger.error(f"❌ Échec scraping après {MAX_RETRIES} tentatives")
    return None


def parse_course_data(data: Dict) -> Optional[Dict]:
    """
    Parse données course PMU.
    
    Args:
        data: Réponse API PMU
        
    Returns:
        Données formatées ou None
    """
    try:
        # CORRECTION: L'API retourne directement la course OU un programme
        # Gérer les deux structures possibles
        
        # Structure 1: API retourne directement la course (URL /RX/CX)
        if 'libelle' in data and 'participants' in data:
            course = data
            hippodrome_data = data.get('hippodrome', {})
            
            parsed = {
                'date': '',  # Pas dans cette structure
                'reunion': int(data.get('numReunion', 0)),
                'course': int(data.get('numOrdre', 0)),
                'hippodrome': hippodrome_data.get('libelleLong', 'INCONNU'),
                'discipline': data.get('specialite', 'TROT'),
                'distance': int(data.get('distance', 0)),
                'monte': data.get('specialite', 'ATTELE'),
                'conditions': data.get('conditions', ''),
                'prix': int(data.get('montantPrix', 0)),
                'nb_partants': int(data.get('nombreDeclaresPartants', 0)),
                'partants': []
            }
        
        # Structure 2: API retourne programme avec réunions (URL /JJMMAAAA)
        elif 'programme' in data:
            programme = data.get('programme', {})
            reunions = programme.get('reunions', [])
            
            if not reunions:
                logger.error("❌ Aucune réunion dans les données")
                return None
            
            reunion = reunions[0]
            courses = reunion.get('courses', [])
            
            if not courses:
                logger.error("❌ Aucune course dans la réunion")
                return None
            
            course = courses[0]
            
            parsed = {
                'date': programme.get('date', ''),
                'reunion': reunion.get('numOfficiel', 0),
                'course': course.get('numOrdre', 0),
                'hippodrome': reunion.get('hippodrome', {}).get('libelleLong', 'INCONNU'),
                'discipline': course.get('libelleDiscipline', 'TROT'),
                'distance': int(course.get('distance', 0)),
                'monte': course.get('libelleMonte', 'ATTELE'),
                'conditions': course.get('conditions', ''),
                'prix': int(course.get('montantPrix', 0)),
                'nb_partants': len(course.get('participants', [])),
                'partants': []
            }
        
        else:
            logger.error("❌ Structure JSON non reconnue")
            return None
        
        # Extraire partants (même logique pour les 2 structures)
        participants = course.get('participants', [])
        
        # Si participants est vide mais nombreDeclaresPartants > 0
        # C'est une course déjà terminée sans détails partants
        if not participants and parsed.get('nb_partants', 0) > 0:
            logger.warning(f"⚠️ Course terminée sans détails partants disponibles")
            logger.warning(f"⚠️ Impossible d'analyser une course passée sans données partants")
            return None
        
        for p in participants:
            try:
                partant = {
                    'numero': int(p.get('numPmu', 0)),
                    'nom': str(p.get('nom', '')),
                    'sexe': str(p.get('sexe', '')),
                    'age': int(p.get('age', 0)),
                    'driver': str(p.get('driver', '')),
                    'entraineur': str(p.get('entraineur', '')),
                    'proprietaire': str(p.get('proprietaire', '')),
                    'musique': str(p.get('musique', '')),
                    'nb_courses': int(p.get('nombreCourses', 0)),
                    'nb_victoires': int(p.get('nombreVictoires', 0)),
                    'nb_places': int(p.get('nombrePlaces', 0)),
                    'gains': int(p.get('gainsCarriere', 0)),
                    'cote': float(p.get('rapport', {}).get('direct', {}).get('rapportDirect', 0.0)),
                    'deferre': bool(p.get('deferre', False)),
                    'oeilleres': bool(p.get('oeilleres', False))
                }
                parsed['partants'].append(partant)
            
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing partant: {e}")
                continue
        
        if not parsed['partants']:
            logger.error("❌ Aucun partant valide")
            return None
        
        logger.info(f"✅ Course parsée: {len(parsed['partants'])} partants")
        return parsed
    
    except Exception as e:
        logger.error(f"❌ Erreur parse_course_data: {e}")
        return None


# ============================================================================
# SCORING
# ============================================================================

def calculer_score_cheval(partant: Dict, course_data: Dict) -> float:
    """
    Calcule score d'un cheval (système 7 facteurs).
    
    Args:
        partant: Données du cheval
        course_data: Données de la course
        
    Returns:
        Score entre 0 et 100
    """
    try:
        score = 0.0
        
        # 1. Ratio victoires (20 points max)
        nb_courses = partant.get('nb_courses', 0)
        nb_victoires = partant.get('nb_victoires', 0)
        if nb_courses > 0:
            ratio_victoires = nb_victoires / nb_courses
            score += ratio_victoires * 20
        
        # 2. Ratio places (15 points max)
        nb_places = partant.get('nb_places', 0)
        if nb_courses > 0:
            ratio_places = nb_places / nb_courses
            score += ratio_places * 15
        
        # 3. Gains moyens (15 points max)
        gains = partant.get('gains', 0)
        if nb_courses > 0 and gains > 0:
            gains_moyen = gains / nb_courses
            # Normaliser (max 50000€ par course)
            score += min(gains_moyen / 50000, 1.0) * 15
        
        # 4. Forme récente via musique (20 points max)
        musique = partant.get('musique', '')
        if musique:
            # Prendre 5 dernières courses
            recent = musique[:5] if len(musique) >= 5 else musique
            forme = 0
            for position in recent:
                if position.isdigit():
                    pos = int(position)
                    if pos == 1:
                        forme += 5
                    elif pos == 2:
                        forme += 3
                    elif pos == 3:
                        forme += 2
                    elif pos <= 5:
                        forme += 1
            # Normaliser sur 20
            score += min(forme / 25 * 20, 20)
        
        # 5. Expérience (10 points max)
        # Optimal: 20-50 courses
        if nb_courses >= 20:
            experience = min(nb_courses / 50, 1.0) * 10
            score += experience
        
        # 6. Âge optimal (10 points max)
        # Optimal: 4-6 ans
        age = partant.get('age', 0)
        if 4 <= age <= 6:
            score += 10
        elif 3 <= age <= 7:
            score += 5
        
        # 7. Équipement (10 points max)
        if partant.get('deferre', False):
            score += 5
        if partant.get('oeilleres', False):
            score += 5
        
        # Normaliser sur 100
        score = min(score, 100.0)
        
        return round(score, 2)
    
    except Exception as e:
        logger.error(f"❌ Erreur calcul score: {e}")
        return 0.0


def scorer_tous_partants(course_data: Dict) -> List[Dict]:
    """
    Score tous les partants et les trie.
    
    Args:
        course_data: Données de la course
        
    Returns:
        Liste partants avec scores, triés
    """
    try:
        partants = course_data.get('partants', [])
        
        if not partants:
            logger.error("❌ Aucun partant à scorer")
            return []
        
        # Calculer scores
        for partant in partants:
            score = calculer_score_cheval(partant, course_data)
            partant['score'] = score
        
        # Trier par score décroissant
        partants.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        logger.info(f"✅ {len(partants)} chevaux scorés")
        
        return partants
    
    except Exception as e:
        logger.error(f"❌ Erreur scorer_tous_partants: {e}")
        return []


# ============================================================================
# PARIS RECOMMANDÉS
# ============================================================================

def generer_paris(top_chevaux: List[Dict], budget: int) -> List[Dict]:
    """
    Génère recommandations de paris selon budget.
    
    Args:
        top_chevaux: Top 5 chevaux
        budget: Budget disponible (5, 10, 15, 20)
        
    Returns:
        Liste de paris recommandés
    """
    try:
        if not top_chevaux or len(top_chevaux) < 3:
            logger.warning("⚠️ Pas assez de chevaux pour paris")
            return []
        
        paris = []
        
        if budget >= 5:
            # Simple Gagnant
            paris.append({
                'type': 'SIMPLE_GAGNANT',
                'chevaux': [top_chevaux[0]['numero']],
                'mise': 3,
                'gain_estime': round(top_chevaux[0].get('cote', 2.0) * 3, 2)
            })
            
            # Simple Placé
            paris.append({
                'type': 'SIMPLE_PLACE',
                'chevaux': [top_chevaux[0]['numero']],
                'mise': 2,
                'gain_estime': round(top_chevaux[0].get('cote', 2.0) * 0.4 * 2, 2)
            })
        
        if budget >= 10:
            # Couplé Gagnant
            if len(top_chevaux) >= 2:
                paris.append({
                    'type': 'COUPLE_GAGNANT',
                    'chevaux': [top_chevaux[0]['numero'], top_chevaux[1]['numero']],
                    'mise': 4,
                    'gain_estime': round((top_chevaux[0].get('cote', 2.0) + top_chevaux[1].get('cote', 2.0)) * 2, 2)
                })
            
            # Simple Placé sécurité
            if len(top_chevaux) >= 2:
                paris.append({
                    'type': 'SIMPLE_PLACE',
                    'chevaux': [top_chevaux[1]['numero']],
                    'mise': 1,
                    'gain_estime': round(top_chevaux[1].get('cote', 2.0) * 0.4 * 1, 2)
                })
        
        if budget >= 15:
            # Trio
            if len(top_chevaux) >= 3:
                paris.append({
                    'type': 'TRIO',
                    'chevaux': [top_chevaux[0]['numero'], top_chevaux[1]['numero'], top_chevaux[2]['numero']],
                    'mise': 5,
                    'gain_estime': round(sum(c.get('cote', 2.0) for c in top_chevaux[:3]) * 3, 2)
                })
        
        if budget >= 20:
            # Quarté
            if len(top_chevaux) >= 4:
                paris.append({
                    'type': 'QUARTE',
                    'chevaux': [top_chevaux[0]['numero'], top_chevaux[1]['numero'], 
                               top_chevaux[2]['numero'], top_chevaux[3]['numero']],
                    'mise': 5,
                    'gain_estime': round(sum(c.get('cote', 2.0) for c in top_chevaux[:4]) * 5, 2)
                })
        
        # Calculer ROI estimé
        total_mise = sum(p['mise'] for p in paris)
        total_gain = sum(p['gain_estime'] for p in paris)
        roi = round((total_gain - total_mise) / total_mise * 100, 2) if total_mise > 0 else 0
        
        logger.info(f"✅ {len(paris)} paris générés, ROI estimé: {roi}%")
        
        return paris
    
    except Exception as e:
        logger.error(f"❌ Erreur generer_paris: {e}")
        return []


# ============================================================================
# GEMINI IA
# ============================================================================

def analyser_avec_gemini(course_data: Dict, top_chevaux: List[Dict]) -> str:
    """
    Analyse course avec Gemini AI.
    
    Args:
        course_data: Données de la course
        top_chevaux: Top 5 chevaux
        
    Returns:
        Analyse textuelle ou message d'erreur
    """
    if not GEMINI_API_KEY:
        logger.warning("⚠️ GEMINI_API_KEY non configurée")
        return "Analyse IA non disponible (clé API manquante)"
    
    try:
        # Cache key
        cache_key = f"{course_data['date']}_R{course_data['reunion']}_C{course_data['course']}"
        
        # Vérifier cache
        if cache_key in cache_gemini:
            cached = cache_gemini[cache_key]
            if cached.get('expires_at', datetime.now()) > datetime.now():
                logger.info(f"📦 Cache Gemini hit: {cache_key}")
                return cached['analyse']
        
        # Préparer prompt
        top_5_text = "\n".join([
            f"{i+1}. #{c['numero']} {c['nom']} - Score: {c['score']}/100, "
            f"Cote: {c['cote']}, Driver: {c['driver']}"
            for i, c in enumerate(top_chevaux[:5])
        ])
        
        prompt = f"""Analyse cette course hippique du {course_data['date']} :

Hippodrome: {course_data['hippodrome']}
Distance: {course_data['distance']}m
{course_data['nb_partants']} partants

TOP 5 CHEVAUX (selon notre algorithme) :
{top_5_text}

Donne une analyse COURTE (3-4 phrases max) avec :
1. Le favori logique
2. Un outsider intéressant
3. Un conseil de pari

Reste concis et pratique."""
        
        # Appeler Gemini
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        
        headers = {'Content-Type': 'application/json'}
        
        payload = {
            'contents': [{
                'parts': [{'text': prompt}]
            }]
        }
        
        response = requests.post(
            f"{url}?key={GEMINI_API_KEY}",
            headers=headers,
            json=payload,
            timeout=config.REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Extraire texte
            candidates = result.get('candidates', [])
            if candidates:
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                if parts:
                    analyse = parts[0].get('text', '')
                    
                    # Mettre en cache
                    cache_gemini[cache_key] = {
                        'analyse': analyse,
                        'expires_at': datetime.now() + timedelta(seconds=config.CACHE_TTL_GEMINI)
                    }
                    
                    logger.info(f"✅ Analyse Gemini générée: {len(analyse)} caractères")
                    return analyse
        
        # Erreur API
        logger.warning(f"⚠️ Gemini API status {response.status_code}")
        return "Analyse IA temporairement indisponible"
    
    except Exception as e:
        logger.error(f"❌ Erreur Gemini: {e}")
        return "Analyse IA non disponible"


# ============================================================================
# ROUTES API
# ============================================================================

@app.route('/')
def index():
    """Page d'accueil."""
    return jsonify({
        "name": "Trot System v8.3 FINAL",
        "version": "8.3",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "race": "/race?date=DDMMYYYY&r=1-9&c=1-16&budget=5|10|15|20",
            "stats": "/stats" if HAS_DATABASE else None
        },
        "features": [
            "Scraping PMU",
            "Scoring 7 facteurs",
            "Gemini IA",
            "Paris optimisés",
            "PostgreSQL" if HAS_DATABASE else "Sans DB"
        ]
    })


@app.route('/health')
def health():
    """Health check."""
    status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "api": "ok",
            "gemini_configured": "yes" if GEMINI_API_KEY else "no",
            "database": "connected" if HAS_DATABASE and test_connection() else "not configured"
        },
        "cache": {
            "courses": len(cache_courses),
            "gemini": len(cache_gemini)
        }
    }
    
    return jsonify(status)


@app.route('/race')
def analyser_course():
    """
    Analyse une course hippique.
    
    Query params:
        - date: DDMMYYYY
        - r: Numéro réunion (1-9)
        - c: Numéro course (1-16)
        - budget: Budget (5, 10, 15, 20) - défaut 20
    """
    try:
        # Récupérer paramètres
        date_str = request.args.get('date', '').strip()
        reunion_str = request.args.get('r', '').strip()
        course_str = request.args.get('c', '').strip()
        budget_str = request.args.get('budget', '20').strip()
        
        # Convertir
        try:
            reunion = int(reunion_str)
            course = int(course_str)
            budget = int(budget_str)
        except ValueError:
            return jsonify({
                "success": False,
                "error": "Paramètres invalides. Format: date=DDMMYYYY&r=1&c=1&budget=20"
            }), 400
        
        # Valider
        is_valid, error_msg = validate_params(date_str, reunion, course, budget)
        if not is_valid:
            return jsonify({
                "success": False,
                "error": error_msg
            }), 400
        
        logger.info(f"🏁 Analyse demandée: {date_str} R{reunion}C{course} Budget: {budget}€")
        
        # Nettoyer cache
        clean_cache()
        
        # Scraper PMU
        data = scrape_pmu_with_retry(date_str, reunion, course)
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Course introuvable. Vérifiez la date, réunion et numéro de course."
            }), 404
        
        # Parser données
        course_data = parse_course_data(data)
        
        if not course_data:
            return jsonify({
                "success": False,
                "error": "Impossible de parser les données de la course."
            }), 500
        
        # Scorer chevaux
        partants_scores = scorer_tous_partants(course_data)
        
        if not partants_scores:
            return jsonify({
                "success": False,
                "error": "Impossible de calculer les scores."
            }), 500
        
        # Top 5
        top_5 = partants_scores[:5]
        
        # Générer paris
        paris = generer_paris(top_5, budget)
        
        # Analyse Gemini
        analyse_ia = analyser_avec_gemini(course_data, top_5)
        
        # Sauvegarder en DB si disponible
        if HAS_DATABASE:
            try:
                with get_db() as db:
                    analyse = Analyse(
                        date_course=date_str,
                        reunion=reunion,
                        course=course,
                        hippodrome=course_data['hippodrome'],
                        discipline=course_data['discipline'],
                        distance=course_data['distance'],
                        nb_partants=course_data['nb_partants'],
                        top_5=[{
                            'numero': c['numero'],
                            'nom': c['nom'],
                            'score': c['score'],
                            'cote': c['cote']
                        } for c in top_5],
                        paris_recommandes=paris,
                        budget=budget,
                        roi_attendu=sum(p['gain_estime'] for p in paris) - budget,
                        analyse_ia=analyse_ia,
                        version='8.3'
                    )
                    db.add(analyse)
                    db.commit()
                    logger.info("✅ Analyse sauvegardée en DB")
            except Exception as e:
                logger.error(f"⚠️ Erreur sauvegarde DB: {e}")
        
        # Réponse
        response = {
            "success": True,
            "course": {
                "date": course_data['date'],
                "reunion": course_data['reunion'],
                "course": course_data['course'],
                "hippodrome": course_data['hippodrome'],
                "discipline": course_data['discipline'],
                "distance": course_data['distance'],
                "nb_partants": course_data['nb_partants']
            },
            "top_5_chevaux": [{
                "position": i + 1,
                "numero": c['numero'],
                "nom": c['nom'],
                "score": c['score'],
                "cote": c['cote'],
                "driver": c['driver'],
                "musique": c['musique']
            } for i, c in enumerate(top_5)],
            "paris_recommandes": paris,
            "budget_total": budget,
            "total_mise": sum(p['mise'] for p in paris),
            "gain_estime_total": sum(p['gain_estime'] for p in paris),
            "roi_estime": round((sum(p['gain_estime'] for p in paris) - sum(p['mise'] for p in paris)) / sum(p['mise'] for p in paris) * 100, 2) if paris else 0,
            "analyse_ia": analyse_ia,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"✅ Analyse terminée: Top={top_5[0]['numero']} Score={top_5[0]['score']}")
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"❌ Erreur /race: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Erreur serveur: {str(e)}"
        }), 500


# Routes Database (si disponible)
if HAS_DATABASE:
    
    @app.route('/stats')
    def get_stats():
        """Statistiques système."""
        try:
            stats = get_db_stats()
            return jsonify({
                "success": True,
                "statistics": stats
            })
        except Exception as e:
            logger.error(f"❌ Erreur /stats: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route('/analyses')
    def get_analyses():
        """Liste des analyses."""
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 50))
            
            with get_db() as db:
                query = db.query(Analyse).order_by(Analyse.created_at.desc())
                total = query.count()
                analyses = query.offset((page - 1) * per_page).limit(per_page).all()
                
                return jsonify({
                    "success": True,
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "analyses": [{
                        "id": a.id,
                        "date_course": a.date_course,
                        "reunion": a.reunion,
                        "course": a.course,
                        "hippodrome": a.hippodrome,
                        "top_5": a.top_5,
                        "roi_attendu": a.roi_attendu,
                        "created_at": a.created_at.isoformat()
                    } for a in analyses]
                })
        
        except Exception as e:
            logger.error(f"❌ Erreur /analyses: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500


# ============================================================================
# INITIALISATION
# ============================================================================

def init_app():
    """Initialisation au démarrage (compatible Flask 3.0)."""
    try:
        logger.info("🚀 Initialisation Trot System v8.3")
        
        # Initialiser database si disponible
        if HAS_DATABASE and DATABASE_URL:
            success = init_database()
            if success:
                logger.info("✅ Database initialisée")
                # Nettoyer cache expiré
                clean_expired_cache()
            else:
                logger.warning("⚠️ Database non disponible")
        else:
            logger.warning("⚠️ Base de données non configurée - Mode dégradé")
        
        # Afficher config
        logger.info(f"Gemini: {'✅ Configuré' if GEMINI_API_KEY else '❌ Non configuré'}")
        logger.info(f"Database: {'✅ Activé' if HAS_DATABASE else '❌ Désactivé'}")
        logger.info("✅ Application prête")
    
    except Exception as e:
        logger.error(f"❌ Erreur initialisation: {e}")


# Appeler initialisation au démarrage (Flask 3.0 compatible)
with app.app_context():
    init_app()


# ============================================================================
# POINT D'ENTRÉE
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('ENVIRONMENT', 'production') != 'production'
    
    logger.info(f"🚀 Démarrage sur port {port}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
