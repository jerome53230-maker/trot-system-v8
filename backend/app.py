"""
Trot System v8.3 FINAL CORRIGÉ - Backend API Professionnel
Corrections: Endpoint /participants pour données complètes
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


def validate_params(date: str, reunion: int, course: int, budget: int) -> Tuple[bool, str]:
    """
    Valide paramètres requête.
    
    Returns:
        (valid, error_message)
    """
    # Date
    if not validate_date(date):
        return False, "Date invalide. Format: JJMMAAAA (ex: 22122025)"
    
    # Réunion
    if not isinstance(reunion, int) or reunion < 1 or reunion > 9:
        return False, "Réunion doit être entre 1 et 9"
    
    # Course
    if not isinstance(course, int) or course < 1 or course > 16:
        return False, "Course doit être entre 1 et 16"
    
    # Budget
    if budget not in [5, 10, 15, 20]:
        return False, "Budget doit être 5, 10, 15 ou 20€"
    
    return True, ""


# ============================================================================
# API PMU - SCRAPING AVEC ENDPOINT /participants
# ============================================================================

def scrape_pmu_with_retry(date_str: str, reunion: int, course: int) -> Optional[Dict]:
    """
    Scrape API PMU avec retry automatique.
    Utilise 2 endpoints: infos course + participants détaillés
    
    Args:
        date_str: Date format DDMMYYYY
        reunion: Numéro réunion (1-9)
        course: Numéro course (1-16)
        
    Returns:
        Données course avec participants ou None si échec
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
            # URL 1: Infos course de base
            url_course = f"{BASE_URL}/programme/{date_str}/R{reunion}/C{course}"
            
            logger.info(f"🌐 Scraping PMU course (tentative {attempt + 1}/{MAX_RETRIES}): {url_course}")
            
            response_course = requests.get(url_course, timeout=config.REQUEST_TIMEOUT)
            
            if response_course.status_code != 200:
                if response_course.status_code == 404:
                    logger.warning(f"⚠️ Course introuvable (404): {url_course}")
                    return None
                else:
                    logger.warning(f"⚠️ Status {response_course.status_code}: {url_course}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                        continue
                    return None
            
            data_course = response_course.json()
            
            # Valider données course
            if not data_course:
                logger.warning(f"⚠️ Données course vides: {url_course}")
                return None
            
            # URL 2: Participants (CRITIQUE pour avoir les détails)
            url_participants = f"{BASE_URL}/programme/{date_str}/R{reunion}/C{course}/participants"
            
            logger.info(f"🌐 Scraping PMU participants: {url_participants}")
            
            response_participants = requests.get(url_participants, timeout=config.REQUEST_TIMEOUT)
            
            if response_participants.status_code != 200:
                logger.warning(f"⚠️ Participants non disponibles (status {response_participants.status_code})")
                logger.warning(f"⚠️ Course peut-être terminée ou données pas encore publiées")
                return None
            
            data_participants = response_participants.json()
            
            # Fusionner les données
            data_course['participants'] = data_participants.get('participants', [])
            
            if not data_course['participants']:
                logger.warning(f"⚠️ Liste participants vide")
                logger.warning(f"⚠️ Course terminée ou données pas disponibles")
                return None
            
            # Mettre en cache
            cache_courses[cache_key] = {
                'data': data_course,
                'expires_at': datetime.now() + timedelta(seconds=config.CACHE_TTL_PMU)
            }
            
            logger.info(f"✅ Scraping réussi: {cache_key} - {len(data_course['participants'])} participants")
            return data_course
        
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
    Parse données course PMU avec endpoint /participants.
    
    Args:
        data: Réponse API PMU fusionnée (course + participants)
        
    Returns:
        Données formatées ou None
    """
    try:
        # La course retourne directement les infos
        # participants vient de l'endpoint /participants
        
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
        
        # Extraire partants (structure endpoint /participants)
        participants = data.get('participants', [])
        
        if not participants:
            logger.error("❌ Aucun partant dans les données")
            return None
        
        for p in participants:
            try:
                # Structure de l'endpoint /participants
                gains_data = p.get('gainsParticipant', {})
                rapport_direct = p.get('dernierRapportDirect', {})
                
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
                    'gains': int(gains_data.get('gainsCarriere', 0)),
                    'cote': float(rapport_direct.get('rapport', 0.0)),
                    'deferre': 'DEFERRE' in str(p.get('deferre', '')).upper(),
                    'oeilleres': 'AVEC' in str(p.get('oeilleres', '')).upper()
                }
                parsed['partants'].append(partant)
            
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing partant {p.get('numPmu', '?')}: {e}")
                continue
        
        if not parsed['partants']:
            logger.error("❌ Aucun partant valide après parsing")
            return None
        
        logger.info(f"✅ Course parsée: {len(parsed['partants'])} partants")
        return parsed
    
    except Exception as e:
        logger.error(f"❌ Erreur parse_course_data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


# ============================================================================
# SCORING 7 FACTEURS
# ============================================================================

def calculer_score_cheval(cheval: Dict, all_chevaux: List[Dict]) -> float:
    """
    Score sophistiqué 7 facteurs.
    
    Facteurs:
    1. Musique (35%) - Forme récente
    2. Taux victoire (15%) - Régularité gagne
    3. Taux places (15%) - Régularité places
    4. Gains carrière (10%) - Niveau général
    5. Cote (15%) - Confiance public
    6. Driver (5%) - Qualité pilote
    7. Déferre/Oeillères (5%) - Équipement
    
    Returns:
        Score 0-100
    """
    score = 0.0
    
    # 1. MUSIQUE (35 points)
    musique = cheval.get('musique', '')
    if musique:
        notes_musique = []
        for char in musique[:6]:  # 6 dernières courses
            if char.isdigit():
                pos = int(char)
                if pos == 1:
                    notes_musique.append(10)
                elif pos == 2:
                    notes_musique.append(7)
                elif pos == 3:
                    notes_musique.append(5)
                elif pos <= 5:
                    notes_musique.append(3)
                else:
                    notes_musique.append(1)
            elif char.lower() == 'a':
                notes_musique.append(8)  # Arrivé (bonne perf)
            elif char.lower() == 'd':
                notes_musique.append(0)  # Disqualifié
            elif char.lower() == 'm':
                notes_musique.append(2)  # Monté (moins bon)
        
        if notes_musique:
            # Pondération: courses récentes = plus important
            weights = [0.35, 0.25, 0.20, 0.10, 0.07, 0.03]
            weighted_score = sum(n * w for n, w in zip(notes_musique, weights[:len(notes_musique)]))
            score += weighted_score * 3.5  # Sur 35 points
    
    # 2. TAUX VICTOIRE (15 points)
    nb_courses = cheval.get('nb_courses', 0)
    nb_victoires = cheval.get('nb_victoires', 0)
    if nb_courses > 0:
        taux_victoire = nb_victoires / nb_courses
        score += taux_victoire * 15
    
    # 3. TAUX PLACES (15 points)
    nb_places = cheval.get('nb_places', 0)
    if nb_courses > 0:
        taux_places = nb_places / nb_courses
        score += taux_places * 15
    
    # 4. GAINS CARRIÈRE (10 points)
    gains = cheval.get('gains', 0)
    if gains > 0 and all_chevaux:
        gains_max = max((c.get('gains', 0) for c in all_chevaux), default=1)
        if gains_max > 0:
            score += (gains / gains_max) * 10
    
    # 5. COTE (15 points) - Plus faible = mieux
    cote = cheval.get('cote', 999)
    if cote > 0 and cote < 100:
        # Normalisation: cote 2 = 15pts, cote 50 = 3pts
        score_cote = max(0, 15 - (cote - 2) * 0.4)
        score += max(3, min(15, score_cote))
    elif cote == 0:
        score += 7  # Cote non dispo
    
    # 6. DRIVER (5 points)
    driver = cheval.get('driver', '').upper()
    # Drivers top: basé sur stats PMU générales
    top_drivers = ['RAFFIN', 'ABRIVARD', 'NIVARD', 'THOMAIN', 'VERVA', 'BARRIER', 'ROCHARD']
    if any(top in driver for top in top_drivers):
        score += 5
    else:
        score += 2  # Driver standard
    
    # 7. ÉQUIPEMENT (5 points)
    if cheval.get('deferre', False):
        score += 3  # Déferré = souvent mieux
    if cheval.get('oeilleres', False):
        score += 2  # Oeillères = focus
    
    # Normaliser sur 100
    return min(100, max(0, score))


def scorer_tous_partants(partants: List[Dict]) -> List[Dict]:
    """
    Score tous les partants et les trie.
    
    Returns:
        Liste triée par score décroissant
    """
    for cheval in partants:
        cheval['score'] = calculer_score_cheval(cheval, partants)
    
    # Trier par score décroissant
    partants_scores = sorted(partants, key=lambda x: x['score'], reverse=True)
    
    return partants_scores


# ============================================================================
# GÉNÉRATION PARIS
# ============================================================================

def generer_paris(top_chevaux: List[Dict], budget: int) -> Dict:
    """
    Génère paris recommandés selon budget.
    
    Args:
        top_chevaux: Top 5 chevaux triés
        budget: Budget total (5/10/15/20€)
        
    Returns:
        Dict avec paris recommandés
    """
    paris = []
    
    if budget == 5:
        # Budget minimal: focus gagnant
        paris.append({
            'type': 'SIMPLE_GAGNANT',
            'chevaux': [top_chevaux[0]['numero']],
            'mise': 3,
            'gain_estime': round(top_chevaux[0]['cote'] * 3, 2)
        })
        paris.append({
            'type': 'SIMPLE_PLACE',
            'chevaux': [top_chevaux[0]['numero']],
            'mise': 2,
            'gain_estime': round(top_chevaux[0]['cote'] * 0.4 * 2, 2)
        })
    
    elif budget == 10:
        # Budget moyen: gagnant + placé + couplé
        paris.append({
            'type': 'SIMPLE_GAGNANT',
            'chevaux': [top_chevaux[0]['numero']],
            'mise': 4,
            'gain_estime': round(top_chevaux[0]['cote'] * 4, 2)
        })
        paris.append({
            'type': 'SIMPLE_PLACE',
            'chevaux': [top_chevaux[0]['numero']],
            'mise': 3,
            'gain_estime': round(top_chevaux[0]['cote'] * 0.4 * 3, 2)
        })
        paris.append({
            'type': 'COUPLE_GAGNANT',
            'chevaux': [top_chevaux[0]['numero'], top_chevaux[1]['numero']],
            'mise': 3,
            'gain_estime': round(top_chevaux[0]['cote'] * top_chevaux[1]['cote'] * 0.7 * 3, 2)
        })
    
    elif budget == 15:
        # Budget confortable: diversification
        paris.append({
            'type': 'SIMPLE_GAGNANT',
            'chevaux': [top_chevaux[0]['numero']],
            'mise': 5,
            'gain_estime': round(top_chevaux[0]['cote'] * 5, 2)
        })
        paris.append({
            'type': 'COUPLE_GAGNANT',
            'chevaux': [top_chevaux[0]['numero'], top_chevaux[1]['numero']],
            'mise': 4,
            'gain_estime': round(top_chevaux[0]['cote'] * top_chevaux[1]['cote'] * 0.7 * 4, 2)
        })
        paris.append({
            'type': 'COUPLE_PLACE',
            'chevaux': [top_chevaux[0]['numero'], top_chevaux[1]['numero']],
            'mise': 3,
            'gain_estime': round(top_chevaux[0]['cote'] * top_chevaux[1]['cote'] * 0.3 * 3, 2)
        })
        paris.append({
            'type': 'TRIO',
            'chevaux': [top_chevaux[0]['numero'], top_chevaux[1]['numero'], top_chevaux[2]['numero']],
            'mise': 3,
            'gain_estime': round(top_chevaux[0]['cote'] * top_chevaux[1]['cote'] * top_chevaux[2]['cote'] * 0.5 * 3, 2)
        })
    
    else:  # budget == 20
        # Budget max: stratégie complète
        paris.append({
            'type': 'SIMPLE_GAGNANT',
            'chevaux': [top_chevaux[0]['numero']],
            'mise': 5,
            'gain_estime': round(top_chevaux[0]['cote'] * 5, 2)
        })
        paris.append({
            'type': 'SIMPLE_PLACE',
            'chevaux': [top_chevaux[0]['numero']],
            'mise': 3,
            'gain_estime': round(top_chevaux[0]['cote'] * 0.4 * 3, 2)
        })
        paris.append({
            'type': 'COUPLE_GAGNANT',
            'chevaux': [top_chevaux[0]['numero'], top_chevaux[1]['numero']],
            'mise': 4,
            'gain_estime': round(top_chevaux[0]['cote'] * top_chevaux[1]['cote'] * 0.7 * 4, 2)
        })
        paris.append({
            'type': 'TRIO',
            'chevaux': [top_chevaux[0]['numero'], top_chevaux[1]['numero'], top_chevaux[2]['numero']],
            'mise': 4,
            'gain_estime': round(top_chevaux[0]['cote'] * top_chevaux[1]['cote'] * top_chevaux[2]['cote'] * 0.5 * 4, 2)
        })
        paris.append({
            'type': 'MULTI',
            'chevaux': [c['numero'] for c in top_chevaux[:4]],
            'mise': 4,
            'gain_estime': round(sum(c['cote'] for c in top_chevaux[:4]) * 2, 2)
        })
    
    total_mise = sum(p['mise'] for p in paris)
    gain_estime_total = sum(p['gain_estime'] for p in paris)
    roi_estime = round(((gain_estime_total - total_mise) / total_mise) * 100, 2) if total_mise > 0 else 0
    
    return {
        'paris': paris,
        'total_mise': total_mise,
        'gain_estime_total': round(gain_estime_total, 2),
        'roi_estime': roi_estime
    }


# ============================================================================
# GEMINI IA
# ============================================================================

def analyser_avec_gemini(course_data: Dict, top_chevaux: List[Dict]) -> str:
    """
    Analyse avec Gemini AI.
    
    Args:
        course_data: Données course
        top_chevaux: Top 5 chevaux
        
    Returns:
        Analyse textuelle ou message d'erreur
    """
    if not GEMINI_API_KEY:
        return "Analyse IA non disponible (clé API manquante)"
    
    # Vérifier cache
    cache_key = f"gemini_{course_data['hippodrome']}_{course_data['course']}"
    if cache_key in cache_gemini:
        cached = cache_gemini[cache_key]
        if cached.get('expires_at', datetime.now()) > datetime.now():
            logger.info(f"📦 Cache Gemini hit: {cache_key}")
            return cached['data']
    
    try:
        # Préparer prompt
        chevaux_info = "\n".join([
            f"{i+1}. #{c['numero']} {c['nom']} - Score: {c['score']:.1f}/100 - Cote: {c['cote']} - Driver: {c['driver']} - Musique: {c['musique']}"
            for i, c in enumerate(top_chevaux)
        ])
        
        prompt = f"""Analyse cette course de trot:

Hippodrome: {course_data['hippodrome']}
Course: R{course_data['reunion']}C{course_data['course']}
Distance: {course_data['distance']}m
Discipline: {course_data['discipline']}
{course_data['nb_partants']} partants

Top 5 chevaux (par score):
{chevaux_info}

Fais une analyse concise (150 mots max) incluant:
1. Favori logique et pourquoi
2. Outsider à surveiller
3. Configuration de course
4. Conseil de jeu final

Sois direct, professionnel, et pertinent."""

        # Appel Gemini
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        
        headers = {'Content-Type': 'application/json'}
        
        payload = {
            'contents': [{
                'parts': [{'text': prompt}]
            }],
            'generationConfig': {
                'temperature': 0.7,
                'maxOutputTokens': 300
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            analyse = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            
            # Mettre en cache
            cache_gemini[cache_key] = {
                'data': analyse,
                'expires_at': datetime.now() + timedelta(seconds=config.CACHE_TTL_GEMINI)
            }
            
            logger.info(f"✅ Analyse Gemini générée")
            return analyse
        else:
            logger.warning(f"⚠️ Gemini erreur status {response.status_code}")
            return "Analyse IA non disponible (erreur API)"
    
    except Exception as e:
        logger.error(f"❌ Erreur Gemini: {e}")
        return "Analyse IA non disponible (erreur technique)"


# ============================================================================
# ROUTES FLASK
# ============================================================================

@app.route('/', methods=['GET'])
def home():
    """Page d'accueil API."""
    return jsonify({
        'name': 'Trot System v8.3 FINAL CORRIGÉ',
        'version': '8.3',
        'status': 'operational',
        'endpoints': {
            'health': '/health',
            'race': '/race?date=DDMMYYYY&r=1-9&c=1-16&budget=5|10|15|20'
        },
        'features': [
            'Scraping PMU avec endpoint /participants',
            'Scoring 7 facteurs',
            'Gemini IA',
            'Paris optimisés',
            'Cache intelligent'
        ]
    })


@app.route('/health', methods=['GET'])
def health():
    """Health check."""
    clean_cache()  # Nettoyer cache périodiquement
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'components': {
            'api': 'ok',
            'gemini_configured': 'yes' if GEMINI_API_KEY else 'no',
            'database': 'configured' if HAS_DATABASE else 'not configured'
        },
        'cache': {
            'courses': len(cache_courses),
            'gemini': len(cache_gemini)
        }
    })


@app.route('/race', methods=['GET'])
def analyze_race():
    """
    Analyse une course.
    
    Params:
        date (str): Date JJMMAAAA (ex: 22122025)
        r (int): Réunion 1-9
        c (int): Course 1-16
        budget (int, optional): Budget 5/10/15/20€ (défaut: 20)
    """
    try:
        # Récupérer paramètres
        date = request.args.get('date', '')
        reunion = request.args.get('r', type=int, default=0)
        course = request.args.get('c', type=int, default=0)
        budget = request.args.get('budget', type=int, default=20)
        
        logger.info(f"🏁 Analyse demandée: {date} R{reunion}C{course} Budget: {budget}€")
        
        # Valider params
        valid, error_msg = validate_params(date, reunion, course, budget)
        if not valid:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # Scraper PMU (avec endpoint /participants)
        data_raw = scrape_pmu_with_retry(date, reunion, course)
        
        if not data_raw:
            return jsonify({
                'success': False,
                'error': 'Course introuvable. Vérifiez la date, réunion et numéro de course.'
            }), 404
        
        # Parser données
        data_parsed = parse_course_data(data_raw)
        
        if not data_parsed:
            return jsonify({
                'success': False,
                'error': 'Erreur parsing données course.'
            }), 500
        
        # Scorer chevaux
        partants_scores = scorer_tous_partants(data_parsed['partants'])
        top_5 = partants_scores[:5]
        
        # Générer paris
        paris_data = generer_paris(top_5, budget)
        
        # Analyse Gemini
        analyse_ia = analyser_avec_gemini(data_parsed, top_5)
        
        # Résultat
        result = {
            'success': True,
            'course': {
                'date': date,
                'reunion': reunion,
                'course': course,
                'hippodrome': data_parsed['hippodrome'],
                'discipline': data_parsed['discipline'],
                'distance': data_parsed['distance'],
                'nb_partants': data_parsed['nb_partants']
            },
            'top_5_chevaux': [
                {
                    'position': i + 1,
                    'numero': c['numero'],
                    'nom': c['nom'],
                    'score': round(c['score'], 2),
                    'cote': c['cote'],
                    'driver': c['driver'],
                    'musique': c['musique'],
                    'nb_victoires': c['nb_victoires'],
                    'nb_courses': c['nb_courses']
                }
                for i, c in enumerate(top_5)
            ],
            'paris_recommandes': paris_data['paris'],
            'total_mise': paris_data['total_mise'],
            'gain_estime_total': paris_data['gain_estime_total'],
            'roi_estime': paris_data['roi_estime'],
            'analyse_ia': analyse_ia
        }
        
        logger.info(f"✅ Analyse terminée: {date} R{reunion}C{course}")
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"❌ Erreur /race: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Erreur serveur: {str(e)}'
        }), 500


# ============================================================================
# INITIALISATION
# ============================================================================

# Context de l'app pour initialisation
with app.app_context():
    logger.info("🚀 Initialisation Trot System v8.3")
    
    # Base de données
    if HAS_DATABASE:
        try:
            init_database()
            if test_connection():
                logger.info("✅ Base de données connectée")
            else:
                logger.warning("⚠️ Base de données non accessible")
                HAS_DATABASE = False
        except Exception as e:
            logger.warning(f"⚠️ Base de données non configurée: {e}")
            HAS_DATABASE = False
    else:
        logger.warning("⚠️ Base de données non configurée - Mode dégradé")
    
    # Gemini
    if GEMINI_API_KEY:
        logger.info("Gemini: ✅ Configuré")
    else:
        logger.warning("Gemini: ⚠️ Non configuré (analyse IA désactivée)")
    
    logger.info(f"Database: {'✅ Activé' if HAS_DATABASE else '❌ Désactivé'}")
    logger.info("✅ Application prête")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
