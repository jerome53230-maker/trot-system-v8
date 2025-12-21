"""
TROT SYSTEM v8.0 - API FLASK COMPLÈTE STANDALONE
Version avec endpoint /race fonctionnel
Sans dépendances externes
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

# Configuration Flask
app = Flask(__name__)
CORS(app)

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('trot-system')

# Configuration Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Historique simple (JSON en mémoire)
history_store = []

# Cache simple pour scraping
cache = {}

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def scrape_pmu_race(date_str, reunion, course):
    """
    Scrape les données d'une course PMU.
    Version simplifiée sans classe PMUScraper.
    """
    try:
        # Vérifier cache
        cache_key = f"{date_str}-R{reunion}C{course}"
        if cache_key in cache:
            logger.info("✅ Données depuis cache")
            return cache[cache_key]
        
        # URL API PMU
        url = f"https://online.turfinfo.api.pmu.fr/rest/client/1/programme/{date_str}/R{reunion}/C{course}"
        logger.info(f"📡 Récupération course: {url}")
        
        # Requête
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Parser les données essentielles
        race_data = {
            'date': date_str,
            'reunion': reunion,
            'course': course,
            'hippodrome': data.get('libelleLongHippodrome', 'INCONNU'),
            'discipline': data.get('discipline', 'TROT'),
            'distance': data.get('distance', 0),
            'nb_partants': len(data.get('participants', [])),
            'partants': []
        }
        
        # Parser les partants
        for p in data.get('participants', []):
            partant = {
                'numero': p.get('numPmu', 0),
                'nom': p.get('nom', ''),
                'driver': p.get('driver', ''),
                'entraineur': p.get('entraineur', ''),
                'cote': p.get('rapport', {}).get('direct', {}).get('rapportDirect', 0.0),
                'musique': p.get('musique', ''),
                'age': p.get('age', 0),
                'sexe': p.get('sexe', ''),
                'score': 0.0  # Sera calculé
            }
            race_data['partants'].append(partant)
        
        logger.info(f"✅ Course récupérée: {race_data['nb_partants']} partants")
        
        # Cache
        cache[cache_key] = race_data
        
        return race_data
    
    except Exception as e:
        logger.error(f"❌ Erreur scraping: {e}")
        return None


def score_horses(race_data):
    """
    Scoring simplifié des chevaux.
    Version standalone sans ScoringEngine.
    """
    try:
        logger.info(f"🔢 Scoring {race_data['nb_partants']} chevaux...")
        
        for partant in race_data['partants']:
            score = 50.0  # Score de base
            
            # Bonus cote attractive (entre 3 et 15)
            cote = partant.get('cote', 0)
            if 3 <= cote <= 15:
                score += 15
            elif cote < 3:
                score += 5
            
            # Bonus musique récente
            musique = partant.get('musique', '')
            if musique:
                # Compte les '1' dans les 5 dernières courses
                recent = musique[:5] if len(musique) >= 5 else musique
                nb_victoires = recent.count('1')
                score += nb_victoires * 10
            
            # Pénalité si jeune (< 3 ans)
            if partant.get('age', 0) < 3:
                score -= 5
            
            partant['score'] = round(score, 2)
        
        # Trier par score décroissant
        race_data['partants'].sort(key=lambda x: x['score'], reverse=True)
        
        logger.info(f"✅ Scoring terminé. Top 5: {[p['numero'] for p in race_data['partants'][:5]]}")
        
        return race_data
    
    except Exception as e:
        logger.error(f"❌ Erreur scoring: {e}")
        return race_data


def generate_bets(race_data, budget):
    """
    Génère des recommandations de paris.
    Version simplifiée sans stratégie complexe.
    """
    try:
        logger.info(f"💰 Génération paris avec budget {budget}€...")
        
        paris = []
        top_5 = race_data['partants'][:5]
        
        # Vérifier qu'il y a des partants
        if len(top_5) == 0:
            logger.warning("⚠️ Pas de partants, aucun pari généré")
            return []
        
        if budget >= 20:
            # Budget 20€: 3 paris
            paris = [
                {
                    'type': 'SIMPLE_GAGNANT',
                    'chevaux': [top_5[0]['numero']],
                    'mise': 5,
                    'roi_attendu': 2.5,
                    'justification': f"Favori n°{top_5[0]['numero']} - Score {top_5[0]['score']}"
                },
                {
                    'type': 'SIMPLE_PLACE',
                    'chevaux': [top_5[1]['numero']],
                    'mise': 5,
                    'roi_attendu': 1.5,
                    'justification': f"Outsider n°{top_5[1]['numero']} - Score {top_5[1]['score']}"
                },
                {
                    'type': 'COUPLE_PLACE',
                    'chevaux': [top_5[0]['numero'], top_5[1]['numero']],
                    'mise': 10,
                    'roi_attendu': 3.0,
                    'justification': f"Couple {top_5[0]['numero']}-{top_5[1]['numero']}"
                }
            ]
        elif budget >= 10:
            # Budget 10€: 2 paris
            paris = [
                {
                    'type': 'SIMPLE_GAGNANT',
                    'chevaux': [top_5[0]['numero']],
                    'mise': 5,
                    'roi_attendu': 2.5,
                    'justification': f"Favori n°{top_5[0]['numero']}"
                },
                {
                    'type': 'SIMPLE_PLACE',
                    'chevaux': [top_5[1]['numero']],
                    'mise': 5,
                    'roi_attendu': 1.5,
                    'justification': f"Outsider n°{top_5[1]['numero']}"
                }
            ]
        else:
            # Budget 5€: 1 pari
            paris = [
                {
                    'type': 'SIMPLE_GAGNANT',
                    'chevaux': [top_5[0]['numero']],
                    'mise': 5,
                    'roi_attendu': 2.5,
                    'justification': f"Favori n°{top_5[0]['numero']}"
                }
            ]
        
        logger.info(f"✅ {len(paris)} paris générés")
        
        return paris
    
    except Exception as e:
        logger.error(f"❌ Erreur génération paris: {e}")
        return []


def call_gemini(prompt):
    """
    Appelle l'API Gemini.
    Version simplifiée sans GeminiClient avec gestion quota.
    """
    try:
        if not GEMINI_API_KEY:
            logger.warning("⚠️ GEMINI_API_KEY non configurée")
            return "Analyse IA indisponible (clé API manquante). Le système fonctionne sans analyse IA."
        
        import google.generativeai as genai
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        response = model.generate_content(prompt)
        
        return response.text
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Erreur Gemini: {e}")
        
        # Gestion spécifique du quota dépassé
        if "429" in error_msg or "quota" in error_msg.lower():
            return "Analyse IA temporairement indisponible (quota API dépassé). Les recommandations de paris sont basées sur l'algorithme de scoring uniquement."
        
        return f"Analyse IA indisponible. Les recommandations sont basées sur l'algorithme de scoring."


# ============================================================================
# ENDPOINTS API
# ============================================================================

@app.route('/')
def home():
    """Page d'accueil avec documentation API."""
    return jsonify({
        "name": "Trot System v8.0 - Standalone",
        "version": "8.0.0-standalone",
        "description": "API Flask complète standalone pour analyse hippique",
        "status": "operational",
        "endpoints": {
            "/": "GET - Cette page",
            "/health": "GET - Health check",
            "/race": "GET ?date=DDMMYYYY&r=1&c=4&budget=20 - Analyse course",
            "/history": "GET - Historique des analyses"
        }
    })


@app.route('/health')
def health():
    """Health check de l'application."""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "gemini_api_key": "configured" if GEMINI_API_KEY else "missing",
            "cache_entries": len(cache),
            "historique_entries": len(history_store)
        }
        
        return jsonify(health_status), 200
    
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 503


@app.route('/race', methods=['GET'])
def analyze_race():
    """
    Analyse une course et génère recommandations paris.
    
    Query params:
        date: DDMMYYYY (ex: 20122025)
        r: Numéro réunion (1-9)
        c: Numéro course (1-16)
        budget: Budget en euros (5|10|15|20, défaut=20)
    
    Returns:
        JSON avec analyse complète
    """
    try:
        # Extraction paramètres
        date_str = request.args.get('date')
        reunion = request.args.get('r', type=int)
        course = request.args.get('c', type=int)
        budget = request.args.get('budget', default=20, type=int)
        
        # Validation
        if not date_str or not reunion or not course:
            return jsonify({
                "error": "Paramètres manquants",
                "usage": "/race?date=20122025&r=1&c=4&budget=20"
            }), 400
        
        if budget not in [5, 10, 15, 20]:
            return jsonify({
                "error": "Budget invalide (5|10|15|20)"
            }), 400
        
        logger.info(f"📊 Analyse course: {date_str} R{reunion}C{course} (Budget: {budget}€)")
        
        # PHASE 1: Scraping
        logger.info("1️⃣ Scraping PMU...")
        race_data = scrape_pmu_race(date_str, reunion, course)
        
        if not race_data:
            return jsonify({
                "error": "Course introuvable ou données indisponibles",
                "details": "L'API PMU n'a pas retourné de données pour cette course"
            }), 404
        
        # Vérifier qu'il y a des partants
        if race_data['nb_partants'] == 0:
            return jsonify({
                "error": "Course sans partants",
                "details": f"La course {date_str} R{reunion}C{course} n'a pas de partants déclarés",
                "suggestions": [
                    "Vérifiez que la date est correcte (format: DDMMYYYY)",
                    "Vérifiez que la course existe sur PMU.fr",
                    "Essayez une autre réunion ou course",
                    "Les courses futures peuvent ne pas avoir de partants déclarés"
                ]
            }), 404
        
        # PHASE 2: Scoring
        logger.info("2️⃣ Scoring chevaux...")
        race_data = score_horses(race_data)
        
        # PHASE 3: Génération paris
        logger.info("3️⃣ Génération paris...")
        paris_recommandes = generate_bets(race_data, budget)
        
        # PHASE 4: Analyse Gemini (optionnel)
        logger.info("4️⃣ Analyse IA...")
        top_5 = race_data['partants'][:5]
        
        if len(top_5) > 0:
            prompt = f"""Analyse cette course de trot:
Hippodrome: {race_data['hippodrome']}
Distance: {race_data['distance']}m
Nombre de partants: {race_data['nb_partants']}
Top {len(top_5)} chevaux:
{json.dumps([{'numero': p['numero'], 'nom': p['nom'], 'score': p['score'], 'cote': p['cote']} for p in top_5], indent=2)}

Donne une analyse courte (3-4 lignes) avec ton pronostic."""
            
            analyse_ia = call_gemini(prompt)
        else:
            analyse_ia = "Analyse IA indisponible (pas assez de données)"
        
        # Résultat final
        result = {
            "date": date_str,
            "reunion": reunion,
            "course": course,
            "hippodrome": race_data['hippodrome'],
            "distance": race_data['distance'],
            "nb_partants": race_data['nb_partants'],
            "top_5_chevaux": [
                {
                    'numero': p['numero'],
                    'nom': p['nom'],
                    'score': p['score'],
                    'cote': p['cote']
                }
                for p in top_5
            ],
            "paris_recommandes": paris_recommandes,
            "budget_total": budget,
            "analyse_ia": analyse_ia,
            "timestamp": datetime.now().isoformat()
        }
        
        # Sauvegarder dans historique
        history_store.append({
            'date': date_str,
            'reunion': reunion,
            'course': course,
            'hippodrome': race_data['hippodrome'],
            'timestamp': datetime.now().isoformat()
        })
        
        logger.info("✅ Analyse terminée avec succès")
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"❌ Erreur analyse: {e}", exc_info=True)
        return jsonify({
            "error": "Erreur lors de l'analyse",
            "message": str(e)
        }), 500


@app.route('/history')
def get_history():
    """Retourne l'historique des analyses."""
    return jsonify({
        "status": "success",
        "count": len(history_store),
        "history": history_store
    }), 200


# ============================================================================
# GESTION D'ERREURS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Gestion erreur 404."""
    return jsonify({
        "status": "error",
        "code": 404,
        "message": "Endpoint introuvable",
        "available_endpoints": ["/", "/health", "/race", "/history"]
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Gestion erreur 500."""
    logger.error(f"Internal error: {error}")
    return jsonify({
        "status": "error",
        "code": 500,
        "message": "Erreur interne du serveur"
    }), 500


# ============================================================================
# DÉMARRAGE SERVEUR
# ============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Démarrage Trot System v8.0 - Standalone sur port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
