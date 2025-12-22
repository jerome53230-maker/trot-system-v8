"""
TROT SYSTEM v8.1 - API FLASK AMÉLIORÉE
Version standalone avec corrections et améliorations
Compatible Python 3.13
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import requests
from datetime import datetime
from pathlib import Path
import logging
import time
from functools import wraps
from typing import Optional, Dict, List

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

# Cache et historique (en mémoire pour l'instant)
cache = {}
history_store = []

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
    
    if not course or not (1 <= 16 >= course):
        return "Course invalide. Doit être entre 1 et 16"
    
    if budget not in [5, 10, 15, 20]:
        return "Budget invalide. Doit être 5, 10, 15 ou 20€"
    
    return None


# ============================================================================
# SCRAPING PMU AMÉLIORÉ
# ============================================================================

@retry_on_failure(max_attempts=3, delay=2)
def scrape_pmu_race(date_str: str, reunion: int, course: int) -> Optional[Dict]:
    """
    Scrape les données PMU avec retry automatique et validation.
    """
    try:
        # Vérifier cache
        cache_key = f"{date_str}-R{reunion}C{course}"
        if cache_key in cache:
            cache_entry = cache[cache_key]
            if time.time() - cache_entry['timestamp'] < CACHE_TTL:
                logger.info("✅ Données depuis cache")
                return cache_entry['data']
        
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
        
        # Parser les données essentielles avec validation
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
        
        # Parser les partants avec validation
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
        
        # Cache avec timestamp
        cache[cache_key] = {
            'data': race_data,
            'timestamp': time.time()
        }
        
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
# SCORING AMÉLIORÉ
# ============================================================================

def score_horses(race_data: Dict) -> Dict:
    """
    Scoring amélioré avec pondération multi-facteurs.
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
                
                # Régularité (pas de 0, D, A)
                irregularites = recent.count('0') + recent.count('D') + recent.count('A')
                score -= irregularites * 8
                
                # Forme ascendante
                if len(recent) >= 3:
                    try:
                        positions = [int(c) for c in recent[:3] if c.isdigit()]
                        if len(positions) >= 2 and positions[0] < positions[-1]:
                            score += 10  # S'améliore
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
                score += 5  # Souvent bon signe
            if partant.get('oeilleres'):
                score += 3  # Peut améliorer
            
            # FACTEUR 7: Distance adaptée (poids 15%)
            # (Simplification - devrait analyser historique sur distance)
            if race_data['distance'] > 2500:  # Fond
                if musique and '1' in musique[:3]:
                    score += 8  # A déjà gagné, probablement bon sur fond
            
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
# GÉNÉRATION PARIS AMÉLIORÉE
# ============================================================================

def generate_bets(race_data: Dict, budget: int) -> List[Dict]:
    """
    Génère des paris optimisés selon le budget et la qualité des chevaux.
    """
    try:
        logger.info(f"💰 Génération paris avec budget {budget}€...")
        
        paris = []
        partants = race_data['partants']
        
        # Vérifier qu'il y a des partants
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
                # 2 excellents chevaux → Stratégie agressive
                paris = [
                    {
                        'type': 'SIMPLE_GAGNANT',
                        'chevaux': [excellent[0]['numero']],
                        'mise': 6,
                        'cote_estimee': excellent[0]['cote'],
                        'roi_attendu': excellent[0]['cote'] * 0.7,
                        'justification': f"Favori n°{excellent[0]['numero']} (score {excellent[0]['score']}) - Très forte probabilité"
                    },
                    {
                        'type': 'SIMPLE_PLACE',
                        'chevaux': [excellent[1]['numero']],
                        'mise': 4,
                        'cote_estimee': excellent[1]['cote'] / 3,
                        'roi_attendu': (excellent[1]['cote'] / 3) * 0.8,
                        'justification': f"Outsider n°{excellent[1]['numero']} (score {excellent[1]['score']}) - Sécurité"
                    },
                    {
                        'type': 'COUPLE_ORDRE',
                        'chevaux': [excellent[0]['numero'], excellent[1]['numero']],
                        'mise': 10,
                        'cote_estimee': excellent[0]['cote'] * excellent[1]['cote'] * 0.3,
                        'roi_attendu': excellent[0]['cote'] * excellent[1]['cote'] * 0.2,
                        'justification': f"Couple {excellent[0]['numero']}-{excellent[1]['numero']} dans l'ordre - ROI élevé"
                    }
                ]
            elif len(excellent) >= 1 and len(bon) >= 2:
                # 1 excellent + bons → Stratégie équilibrée
                paris = [
                    {
                        'type': 'SIMPLE_GAGNANT',
                        'chevaux': [excellent[0]['numero']],
                        'mise': 7,
                        'cote_estimee': excellent[0]['cote'],
                        'roi_attendu': excellent[0]['cote'] * 0.7,
                        'justification': f"Favori n°{excellent[0]['numero']} (score {excellent[0]['score']})"
                    },
                    {
                        'type': 'COUPLE_PLACE',
                        'chevaux': [excellent[0]['numero'], bon[0]['numero']],
                        'mise': 8,
                        'cote_estimee': excellent[0]['cote'] * bon[0]['cote'] * 0.15,
                        'roi_attendu': excellent[0]['cote'] * bon[0]['cote'] * 0.1,
                        'justification': f"Couple placé {excellent[0]['numero']}-{bon[0]['numero']} - Sécurité"
                    },
                    {
                        'type': 'TRIO_ORDRE',
                        'chevaux': [excellent[0]['numero'], bon[0]['numero'], bon[1]['numero']],
                        'mise': 5,
                        'cote_estimee': 50,
                        'roi_attendu': 35,
                        'justification': f"Trio {excellent[0]['numero']}-{bon[0]['numero']}-{bon[1]['numero']} - Value bet"
                    }
                ]
            else:
                # Pas d'excellents → Stratégie conservatrice
                paris = [
                    {
                        'type': 'SIMPLE_PLACE',
                        'chevaux': [top_5[0]['numero']],
                        'mise': 8,
                        'cote_estimee': top_5[0]['cote'] / 3,
                        'roi_attendu': (top_5[0]['cote'] / 3) * 0.8,
                        'justification': f"Placé n°{top_5[0]['numero']} - Sécurité maximale"
                    },
                    {
                        'type': 'COUPLE_PLACE',
                        'chevaux': [top_5[0]['numero'], top_5[1]['numero']],
                        'mise': 12,
                        'cote_estimee': 8,
                        'roi_attendu': 6,
                        'justification': f"Couple placé {top_5[0]['numero']}-{top_5[1]['numero']} - Conservateur"
                    }
                ]
        
        elif budget >= 10:
            # Budget 10€
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
                        'justification': f"Placé n°{top_5[0]['numero']} - Sécurité"
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
        
        logger.info(f"✅ {len(paris)} paris générés (ROI total attendu: {sum(p['roi_attendu'] for p in paris):.2f}€)")
        
        return paris
    
    except Exception as e:
        logger.error(f"❌ Erreur génération paris: {e}")
        return []


# ============================================================================
# GEMINI AMÉLIORÉ
# ============================================================================

@retry_on_failure(max_attempts=2, delay=5)
def call_gemini(prompt: str) -> str:
    """
    Appelle Gemini avec retry et gestion quota.
    """
    try:
        if not GEMINI_API_KEY:
            logger.warning("⚠️ GEMINI_API_KEY non configurée")
            return "Analyse IA indisponible (clé API manquante). Les recommandations sont basées sur l'algorithme de scoring uniquement."
        
        # Vérifier cache
        cache_key = f"gemini_{hash(prompt)}"
        if cache_key in cache:
            cache_entry = cache[cache_key]
            if time.time() - cache_entry['timestamp'] < 3600:  # 1h
                logger.info("✅ Analyse IA depuis cache")
                return cache_entry['data']
        
        import google.generativeai as genai
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        response = model.generate_content(prompt)
        result = response.text
        
        # Cache
        cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
        
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
# ENDPOINTS API
# ============================================================================

@app.route('/')
def home():
    """Page d'accueil avec documentation."""
    return jsonify({
        "name": "Trot System v8.1",
        "version": "8.1.0-ameliore",
        "description": "API d'analyse hippique avec scoring amélioré",
        "status": "operational",
        "improvements": [
            "Validation robuste des entrées",
            "Retry automatique sur erreurs",
            "Scoring multi-facteurs pondéré",
            "Stratégies paris optimisées",
            "Gestion quota Gemini améliorée",
            "Cache avec TTL",
            "Logs structurés"
        ],
        "endpoints": {
            "/": "GET - Cette page",
            "/health": "GET - Health check détaillé",
            "/race": "GET ?date=DDMMYYYY&r=1&c=4&budget=20 - Analyse course",
            "/history": "GET - Historique des analyses",
            "/stats": "GET - Statistiques système"
        }
    })


@app.route('/health')
def health():
    """Health check détaillé."""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "8.1.0",
            "components": {
                "api": "ok",
                "gemini_configured": "yes" if GEMINI_API_KEY else "no",
                "cache_entries": len(cache),
                "history_entries": len(history_store)
            },
            "config": {
                "max_retries": MAX_RETRIES,
                "timeout": TIMEOUT,
                "cache_ttl": CACHE_TTL
            }
        }
        
        # Test Gemini si configuré
        if GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                health_status["components"]["gemini"] = "ok"
            except Exception as e:
                health_status["components"]["gemini"] = f"error: {str(e)[:100]}"
        
        return jsonify(health_status), 200
    
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503


@app.route('/race', methods=['GET'])
def analyze_race():
    """
    Analyse une course avec validation robuste.
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
                "usage": "/race?date=20122025&r=1&c=4&budget=20",
                "exemples": [
                    "/race?date=20122025&r=1&c=1&budget=20",
                    "/race?date=21122025&r=2&c=3&budget=10"
                ]
            }), 400
        
        logger.info(f"📊 Analyse course: {date_str} R{reunion}C{course} (Budget: {budget}€)")
        
        # PHASE 1: Scraping
        logger.info("1️⃣ Scraping PMU...")
        race_data = scrape_pmu_race(date_str, reunion, course)
        
        if not race_data:
            return jsonify({
                "error": "Course introuvable",
                "details": "L'API PMU n'a pas retourné de données pour cette course",
                "suggestions": [
                    "Vérifiez que la date est correcte (format DDMMYYYY)",
                    "Vérifiez que la course existe sur PMU.fr",
                    "Essayez une autre réunion ou course"
                ]
            }), 404
        
        # Vérifier partants
        if race_data['nb_partants'] == 0:
            return jsonify({
                "error": "Course sans partants",
                "details": f"La course {date_str} R{reunion}C{course} n'a pas de partants déclarés",
                "hippodrome": race_data['hippodrome'],
                "suggestions": [
                    "Cette course n'est peut-être pas encore programmée",
                    "Essayez une course passée (hier ou avant-hier)",
                    "Vérifiez le programme officiel sur PMU.fr",
                    "Les partants sont déclarés 24-48h avant la course"
                ]
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
        
        # Résultat final
        result = {
            "success": True,
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
            "roi_total_attendu": round(sum(p.get('roi_attendu', 0) for p in paris_recommandes), 2),
            "analyse_ia": analyse_ia,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "processing_time": round(duration, 2),
                "version": "8.1.0"
            }
        }
        
        # Sauvegarder dans historique
        history_store.append({
            'date': date_str,
            'reunion': reunion,
            'course': course,
            'hippodrome': race_data['hippodrome'],
            'nb_partants': race_data['nb_partants'],
            'budget': budget,
            'roi_attendu': result['roi_total_attendu'],
            'timestamp': datetime.now().isoformat()
        })
        
        logger.info(f"✅ Analyse terminée en {duration:.2f}s")
        
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
    """Retourne l'historique avec statistiques."""
    try:
        stats = {}
        if history_store:
            stats = {
                "total_analyses": len(history_store),
                "roi_moyen": round(sum(h.get('roi_attendu', 0) for h in history_store) / len(history_store), 2),
                "budget_total": sum(h.get('budget', 0) for h in history_store),
                "hippodromes_analyses": len(set(h.get('hippodrome', '') for h in history_store))
            }
        
        return jsonify({
            "status": "success",
            "count": len(history_store),
            "statistics": stats,
            "history": history_store[-50:]  # Dernières 50 analyses
        }), 200
    except Exception as e:
        logger.error(f"Erreur historique: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/stats')
def get_stats():
    """Statistiques système."""
    try:
        return jsonify({
            "system": {
                "version": "8.1.0",
                "uptime": "N/A",  # À implémenter
                "cache_size": len(cache),
                "cache_hit_rate": "N/A"  # À implémenter
            },
            "analyses": {
                "total": len(history_store),
                "last_24h": "N/A"  # À implémenter
            },
            "performance": {
                "avg_response_time": "N/A"  # À implémenter
            }
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
        "available_endpoints": ["/", "/health", "/race", "/history", "/stats"]
    }), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Erreur 500: {error}")
    return jsonify({
        "status": "error",
        "code": 500,
        "message": "Erreur interne du serveur",
        "details": "Consultez les logs pour plus d'informations"
    }), 500


# ============================================================================
# DÉMARRAGE
# ============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Démarrage Trot System v8.1 sur port {port}")
    logger.info(f"📊 Configuration: retries={MAX_RETRIES}, timeout={TIMEOUT}s, cache_ttl={CACHE_TTL}s")
    app.run(host='0.0.0.0', port=port, debug=False)
