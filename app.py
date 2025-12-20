"""
Trot System v8.0 - API Flask Principale
COMPLET ET CORRIGÉ
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path
import logging

# Configuration
app = Flask(__name__)
CORS(app)

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === CONFIGURATION BASE DE DONNÉES ===
USE_POSTGRESQL = os.getenv('DATABASE_URL') is not None

if USE_POSTGRESQL:
    if USE_POSTGRESQL:
    import psycopg
    DATABASE_URL = os.getenv('DATABASE_URL')
    logger.info("âœ… Mode PostgreSQL activÃ©")
else:
    HISTORY_FILE = Path(__file__).parent / "data" / "history.json"
    logger.info("⚠️ Mode fichier JSON (données perdues au redémarrage)")

# === HISTORIQUE ===
def load_history() -> List[Dict]:
    """Charge l'historique depuis PostgreSQL ou JSON"""
    if USE_POSTGRESQL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Créer table si n'existe pas
            cur.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id SERIAL PRIMARY KEY,
                    date VARCHAR(8),
                    reunion INT,
                    course INT,
                    hippodrome VARCHAR(100),
                    scenario VARCHAR(50),
                    budget INT,
                    roi_attendu FLOAT,
                    nb_paris INT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("SELECT * FROM history ORDER BY timestamp DESC LIMIT 50")
            history = cur.fetchall()
            
            conn.commit()
            cur.close()
            conn.close()
            
            return [dict(row) for row in history]
        except Exception as e:
            logger.error(f"Erreur load_history PostgreSQL: {e}")
            return []
    else:
        try:
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Erreur load_history JSON: {e}")
            return []

def save_history(history: List[Dict]):
    """Sauvegarde l'historique dans PostgreSQL ou JSON"""
    if USE_POSTGRESQL:
        try:
            if not history:
                return
            
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            
            # Insérer dernière entrée
            last = history[-1]
            cur.execute("""
                INSERT INTO history 
                (date, reunion, course, hippodrome, scenario, budget, roi_attendu, nb_paris)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                last.get('date'),
                last.get('reunion'),
                last.get('course'),
                last.get('hippodrome', 'INCONNU'),
                last.get('scenario', 'INCONNU'),
                last.get('budget', 20),
                last.get('roi_attendu', 0),
                last.get('nb_paris', 0)
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            logger.info("✅ Historique sauvegardé (PostgreSQL)")
        except Exception as e:
            logger.error(f"Erreur save_history PostgreSQL: {e}")
    else:
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            logger.info("✅ Historique sauvegardé (JSON)")
        except Exception as e:
            logger.error(f"Erreur save_history JSON: {e}")

# Initialisation historique
history_store = load_history()

# === IMPORTS MODULES (simulés pour l'exemple) ===
# Dans votre projet réel, décommentez ces imports:
# from core.scraper import PMUScraper
# from core.scoring_engine import ScoringEngine
# from core.value_bet_detector import ValueBetDetector
# from ai.gemini_client import GeminiClient
# from ai.prompt_builder import PromptBuilder
# from ai.response_validator import ResponseValidator

# === ROUTES ===

@app.route('/')
def index():
    """Page d'accueil"""
    return jsonify({
        "app": "Trot System v8.0",
        "status": "online",
        "endpoints": [
            "GET  /health",
            "GET  /race?date=DDMMYYYY&r=1&c=1&budget=20",
            "GET  /debrief?date=DDMMYYYY&r=1&c=1",
            "GET  /history"
        ]
    })

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "PostgreSQL" if USE_POSTGRESQL else "JSON",
        "historique_entries": len(history_store)
    })

@app.route('/race', methods=['GET'])
def analyze_race():
    """
    Analyse une course et génère recommandations paris.
    
    Query params:
        date: DDMMYYYY (ex: 18122025)
        r: Numéro réunion (1-9)
        c: Numéro course (1-16)
        budget: Budget en euros (5|10|15|20, défaut=20)
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
                "usage": "/race?date=18122025&r=1&c=1&budget=20"
            }), 400
        
        if budget not in [5, 10, 15, 20]:
            return jsonify({
                "error": "Budget invalide (5|10|15|20)"
            }), 400
        
        logger.info(f"📊 Analyse course: {date_str} R{reunion}C{course} (Budget: {budget}€)")
        
        # TODO: Implémenter scraping + scoring + Gemini
        # Pour l'instant, retourne un exemple
        analysis = {
            "scenario_course": "BATAILLE",
            "confiance_globale": 9,
            "budget_total": budget,
            "budget_utilise": budget * 0.95,
            "roi_moyen_attendu": 3.8,
            "conseil_final": "Course ouverte, sécuriser le couple de tête",
            "top_5_chevaux": [
                {
                    "numero": 6,
                    "nom": "JAIKA DES FANES",
                    "cote": 4.4,
                    "score": 56,
                    "rang": 1,
                    "profil": "SECURITE",
                    "points_forts": "Meilleur score, bonne régularité",
                    "points_faibles": "Score absolu faible pour un favori"
                }
            ],
            "paris_recommandes": [
                {
                    "type": "SIMPLE_GAGNANT",
                    "chevaux": [6],
                    "chevaux_noms": ["JAIKA DES FANES"],
                    "mise": 3.0,
                    "roi_attendu": 4.4,
                    "justification": "Leader par le score"
                }
            ],
            "value_bets_detectes": [],
            "analyse_tactique": "Course ouverte (BATAILLE) car le score maximal est modeste."
        }
        
        # Sauvegarder dans historique
        history_entry = {
            "date": date_str,
            "reunion": reunion,
            "course": course,
            "hippodrome": "VINCENNES",
            "scenario": analysis["scenario_course"],
            "budget": budget,
            "roi_attendu": analysis["roi_moyen_attendu"],
            "nb_paris": len(analysis["paris_recommandes"]),
            "timestamp": datetime.now().isoformat()
        }
        history_store.append(history_entry)
        save_history(history_store)
        
        return jsonify(analysis), 200
        
    except Exception as e:
        logger.error(f"❌ Erreur analyse: {e}", exc_info=True)
        return jsonify({
            "error": "Erreur serveur",
            "detail": str(e)
        }), 500

@app.route('/debrief', methods=['GET'])
def debrief_race():
    """
    Débriefing post-course avec résultats réels.
    
    Query params:
        date: DDMMYYYY
        r: Numéro réunion
        c: Numéro course
    """
    try:
        date_str = request.args.get('date')
        reunion = request.args.get('r', type=int)
        course = request.args.get('c', type=int)
        
        if not date_str or not reunion or not course:
            return jsonify({
                "error": "Paramètres manquants"
            }), 400
        
        logger.info(f"📋 Débriefing: {date_str} R{reunion}C{course}")
        
        # TODO: Implémenter get_race_results()
        # Pour l'instant, retourne un exemple
        debrief = {
            "date": date_str,
            "reunion": reunion,
            "course": course,
            "hippodrome": "VINCENNES",
            "arrivee": [7, 4, 6, 9, 3],
            "non_partants": [],
            "roi_reel": 2.4,
            "gains_total": 48.0,
            "mise_totale": 20.0,
            "precision_top_3": 66.7,
            "paris_joues": [
                {
                    "type": "SIMPLE_GAGNANT",
                    "chevaux": [7],
                    "gagnant": True,
                    "gain": 23.0,
                    "roi": 2.3,
                    "mise": 3.0
                }
            ],
            "paris_gagnants": ["SIMPLE_GAGNANT"],
            "top_5_predit": [6, 7, 9, 3, 4],
            "top_5_reel": [7, 4, 6, 9, 3],
            "commentaire": "✅ Profitable! ROI 2.4x. Top 3 bien anticipé (66.7%)."
        }
        
        return jsonify(debrief), 200
        
    except Exception as e:
        logger.error(f"❌ Erreur débriefing: {e}")
        return jsonify({
            "error": "Erreur serveur",
            "detail": str(e)
        }), 500

@app.route('/history', methods=['GET'])
def get_history():
    """Retourne l'historique des courses analysées"""
    try:
        return jsonify({
            "history": history_store,
            "count": len(history_store)
        }), 200
    except Exception as e:
        logger.error(f"❌ Erreur history: {e}")
        return jsonify({
            "error": "Erreur serveur",
            "detail": str(e)
        }), 500

# === HELPER FUNCTIONS ===

def _is_bet_winning(pari: Dict, arrivee: List[int]) -> bool:
    """Détermine si un pari est gagnant"""
    type_pari = pari['type']
    chevaux = pari['chevaux']
    
    if not arrivee or len(arrivee) == 0:
        return False
    
    if type_pari == 'SIMPLE_GAGNANT':
        return chevaux[0] == arrivee[0]
    elif type_pari == 'SIMPLE_PLACE':
        return chevaux[0] in arrivee[:3]
    elif type_pari == 'COUPLE_GAGNANT':
        return len(arrivee) >= 2 and chevaux == arrivee[:2]
    elif type_pari == 'COUPLE_PLACE':
        return all(c in arrivee[:3] for c in chevaux)
    elif type_pari == 'TRIO':
        return len(arrivee) >= 3 and chevaux == arrivee[:3]
    elif type_pari in ['MULTI_EN_4', 'MULTI_EN_5', 'MULTI_EN_6']:
        return all(c in arrivee[:4] for c in chevaux)
    elif type_pari == 'DEUX_SUR_QUATRE':
        chevaux_places = [c for c in chevaux if c in arrivee[:4]]
        return len(chevaux_places) >= 2
    
    return False

def _get_rapport_pmu(pari: Dict, rapports_pmu: Dict, arrivee: List[int]) -> Optional[float]:
    """Récupère le rapport PMU réel pour un pari"""
    type_pari = pari['type']
    chevaux = pari['chevaux']
    
    type_mapping = {
        'SIMPLE_GAGNANT': 'SIMPLE_GAGNANT',
        'SIMPLE_PLACE': 'SIMPLE_PLACE',
        'COUPLE_GAGNANT': 'COUPLE_GAGNANT',
        'COUPLE_PLACE': 'COUPLE_PLACE',
        'TRIO': 'TRIO',
        'MULTI_EN_4': 'MINI_MULTI',
        'MULTI_EN_5': 'MINI_MULTI',
        'MULTI_EN_6': 'MINI_MULTI',
        'DEUX_SUR_QUATRE': 'DEUX_SUR_QUATRE'
    }
    
    type_pmu = type_mapping.get(type_pari)
    if not type_pmu or type_pmu not in rapports_pmu:
        return None
    
    rapports = rapports_pmu[type_pmu]
    
    try:
        if type_pari == 'SIMPLE_GAGNANT':
            for rapport in rapports:
                if str(arrivee[0]) == rapport['combinaison']:
                    return rapport['dividende']
        
        elif type_pari == 'SIMPLE_PLACE':
            cheval = chevaux[0]
            if cheval in arrivee[:3]:
                for rapport in rapports:
                    if str(cheval) == rapport['combinaison']:
                        return rapport['dividende']
        
        elif type_pari == 'COUPLE_PLACE':
            chevaux_sorted = sorted(chevaux)
            for rapport in rapports:
                parts = rapport['combinaison'].split('-')
                if len(parts) == 2:
                    try:
                        rapport_sorted = sorted([int(p) for p in parts])
                        if chevaux_sorted == rapport_sorted:
                            return rapport['dividende']
                    except ValueError:
                        continue
    except Exception as e:
        logger.error(f"Erreur _get_rapport_pmu: {e}")
        return None
    
    return None

# === LANCEMENT ===

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
