# ============================================================================
# TROT SYSTEM v8.0 - API FLASK PRINCIPALE (OPTIMISÉ)
# ============================================================================

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import json
from datetime import datetime, date
from typing import Optional, List, Dict
from pathlib import Path
import logging
import time
import sys
import importlib

# === FORCE RELOAD MODULES (éviter cache Python/Gunicorn) ===
# CRITIQUE: Gunicorn garde modules en mémoire entre requêtes
# Solution: Forcer reload à chaque démarrage
modules_to_reload = ['core.scraper', 'core.scoring_engine', 'ai.gemini_client']
for mod_name in modules_to_reload:
    if mod_name in sys.modules:
        try:
            importlib.reload(sys.modules[mod_name])
            print(f"🔄 Module {mod_name} rechargé")
        except Exception as e:
            print(f"⚠️ Impossible de recharger {mod_name}: {e}")

# Imports modules internes
from core.scraper import PMUScraper
from core.scoring_engine import ScoringEngine
from core.value_bet_detector import ValueBetDetector
from ai.gemini_client import GeminiClient
from ai.prompt_builder import PromptBuilder
from ai.response_validator import ResponseValidator
from models.bet import RaceAnalysis, Debrief
from utils.logger import setup_logger

# Configuration
app = Flask(__name__)
CORS(app)

# Logger (initialiser AVANT métriques)
logger = setup_logger("trot-system", level=os.getenv("LOG_LEVEL", "INFO"))

# Métriques Prometheus (après logger)
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client non installé, métriques désactivées")

# === MÉTRIQUES PROMETHEUS ===
if PROMETHEUS_AVAILABLE:
    REQUESTS_TOTAL = Counter(
        'trot_requests_total',
        'Total des requêtes',
        ['endpoint', 'status']
    )
    REQUEST_DURATION = Histogram(
        'trot_request_duration_seconds',
        'Durée des requêtes',
        ['endpoint']
    )
    GEMINI_CALLS = Counter(
        'trot_gemini_calls_total',
        'Appels API Gemini',
        ['status']
    )
    RACE_ANALYSES = Counter(
        'trot_race_analyses_total',
        'Nombre d\'analyses de courses'
    )
    CACHE_HITS = Counter(
        'trot_cache_hits_total',
        'Cache hits scraper'
    )

# === HISTORIQUE PERSISTANT (JSON) ===
HISTORY_FILE = Path(__file__).parent / "data" / "history.json"

def load_history() -> List[Dict]:
    """Charge l'historique depuis le fichier JSON."""
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"✓ Historique chargé: {len(data)} entrées")
                return data
        return []
    except Exception as e:
        logger.error(f"Erreur chargement historique: {e}")
        return []

def save_history(history: List[Dict]):
    """Sauvegarde l'historique dans le fichier JSON."""
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        logger.debug(f"Historique sauvegardé: {len(history)} entrées")
    except Exception as e:
        logger.error(f"Erreur sauvegarde historique: {e}")

# Initialisation composants
try:
    scraper = PMUScraper()
    # Cache désactivé dans le scraper lui-même
    
    scoring_engine = ScoringEngine()
    value_detector = ValueBetDetector()
    gemini_client = GeminiClient()
    prompt_builder = PromptBuilder()
    response_validator = ResponseValidator()
    
    logger.info("✓ Tous les composants initialisés")
except Exception as e:
    logger.error(f"❌ Erreur initialisation: {e}")
    raise

# Chargement historique persistant
history_store = load_history()

# === HOOKS MÉTRIQUES ===
if PROMETHEUS_AVAILABLE:
    @app.before_request
    def before_request():
        """Hook avant chaque requête pour métriques."""
        request.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        """Hook après chaque requête pour métriques."""
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            endpoint = request.endpoint or 'unknown'
            REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)
            REQUESTS_TOTAL.labels(
                endpoint=endpoint,
                status=response.status_code
            ).inc()
        return response

# ============================================================================
# ENDPOINTS API
# ============================================================================

@app.route('/')
def home():
    """Page d'accueil avec documentation API."""
    return jsonify({
        "name": "Trot System v8.0",
        "version": "8.0.0",
        "description": "Système d'analyse de courses hippiques avec IA Gemini",
        "endpoints": {
            "/race": "GET ?date=DDMMYYYY&r=1&c=4&budget=20 - Analyse course",
            "/debrief": "GET ?date=DDMMYYYY&r=1&c=4 - Débriefing post-course",
            "/history": "GET - Historique analyses",
            "/health": "GET - Health check"
        }
    })


@app.route('/health')
def health():
    """Health check."""
    try:
        # Test connexion Gemini
        gemini_ok = gemini_client.test_connection()
        
        return jsonify({
            "status": "healthy" if gemini_ok else "degraded",
            "gemini_api": "ok" if gemini_ok else "error",
            "historique_entries": len(history_store),
            "cache_enabled": False,  # Désactivé pour debug
            "cache_note": "Cache désactivé en mode debug",
            "timestamp": datetime.now().isoformat()
        }), 200 if gemini_ok else 503
    
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 503


@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    """Note: Cache désactivé en mode debug."""
    return jsonify({
        "status": "info",
        "message": "Cache désactivé en mode debug - aucune action nécessaire",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/diagnostic')
def diagnostic_pmu():
    """Endpoint de diagnostic de l'API PMU."""
    import requests
    
    # Configuration
    date_str = request.args.get('date', '17122025')
    reunion = int(request.args.get('r', 1))
    course = int(request.args.get('c', 8))
    
    base_url = "https://online.turfinfo.api.pmu.fr/rest/client/1"
    results = {
        "date": date_str,
        "reunion": reunion,
        "course": course,
        "timestamp": datetime.now().isoformat(),
        "tests": []
    }
    
    # Test 1: Endpoint programme principal
    test1 = {
        "name": "Endpoint Programme Principal",
        "url": f"{base_url}/programme/{date_str}/R{reunion}/C{course}",
        "status": None,
        "analysis": []
    }
    
    try:
        r1 = requests.get(test1["url"], timeout=15)
        test1["status"] = r1.status_code
        
        if r1.status_code == 200:
            data1 = r1.json()
            test1["analysis"].append(f"Type réponse: {type(data1).__name__}")
            
            if isinstance(data1, dict):
                test1["analysis"].append(f"Clés principales: {list(data1.keys())[:10]}")
                
                if 'participants' in data1:
                    part = data1['participants']
                    test1["analysis"].append(f"✓ 'participants' trouvé - Type: {type(part).__name__}")
                    
                    if isinstance(part, list) and len(part) > 0:
                        first = part[0]
                        test1["analysis"].append(f"Liste de {len(part)} éléments")
                        test1["analysis"].append(f"Premier élément: {type(first).__name__}")
                        
                        if isinstance(first, dict):
                            test1["analysis"].append(f"✅ FORMAT CORRECT - Dict avec clés: {list(first.keys())[:5]}")
                            test1["result"] = "SUCCESS"
                        elif isinstance(first, str):
                            test1["analysis"].append(f"❌ PROBLÈME - String: '{first[:50]}'")
                            test1["result"] = "FAIL"
                        else:
                            test1["analysis"].append(f"❌ Format inconnu")
                            test1["result"] = "UNKNOWN"
                else:
                    test1["analysis"].append("⚠️ Pas de 'participants' dans réponse")
                    test1["result"] = "NO_PARTICIPANTS"
    except Exception as e:
        test1["analysis"].append(f"❌ Erreur: {str(e)}")
        test1["result"] = "ERROR"
    
    results["tests"].append(test1)
    
    # Test 2: Endpoint participants séparé
    test2 = {
        "name": "Endpoint Participants Séparé",
        "url": f"{base_url}/programme/{date_str}/R{reunion}/C{course}/participants",
        "status": None,
        "analysis": []
    }
    
    try:
        r2 = requests.get(test2["url"], timeout=15)
        test2["status"] = r2.status_code
        
        if r2.status_code == 200:
            data2 = r2.json()
            test2["analysis"].append(f"Type réponse: {type(data2).__name__}")
            
            if isinstance(data2, list):
                test2["analysis"].append(f"✓ Liste directe - {len(data2)} éléments")
                if len(data2) > 0:
                    first = data2[0]
                    test2["analysis"].append(f"Premier élément: {type(first).__name__}")
                    
                    if isinstance(first, dict):
                        test2["analysis"].append(f"✅ FORMAT CORRECT - Clés: {list(first.keys())[:5]}")
                        test2["result"] = "SUCCESS"
                    else:
                        test2["analysis"].append(f"❌ PROBLÈME - {type(first).__name__}")
                        test2["result"] = "FAIL"
                        
            elif isinstance(data2, dict):
                test2["analysis"].append(f"✓ Dict - Clés: {list(data2.keys())}")
                
                for key in ['participants', 'participant', 'partants', 'chevaux']:
                    if key in data2:
                        part = data2[key]
                        test2["analysis"].append(f"✓ Trouvé sous '{key}' - Type: {type(part).__name__}")
                        
                        if isinstance(part, list) and len(part) > 0:
                            first = part[0]
                            if isinstance(first, dict):
                                test2["analysis"].append(f"✅ FORMAT CORRECT")
                                test2["result"] = "SUCCESS"
                            else:
                                test2["analysis"].append(f"❌ PROBLÈME")
                                test2["result"] = "FAIL"
                        break
    except Exception as e:
        test2["analysis"].append(f"❌ Erreur: {str(e)}")
        test2["result"] = "ERROR"
    
    results["tests"].append(test2)
    
    # Test 3: Performances détaillées
    test3 = {
        "name": "Endpoint Performances Détaillées",
        "url": f"{base_url}/programme/{date_str}/R{reunion}/C{course}/performances-detaillees/pretty",
        "status": None,
        "analysis": []
    }
    
    try:
        r3 = requests.get(test3["url"], timeout=15)
        test3["status"] = r3.status_code
        
        if r3.status_code == 200:
            data3 = r3.json()
            test3["analysis"].append(f"Type réponse: {type(data3).__name__}")
            
            if isinstance(data3, dict):
                test3["analysis"].append(f"Clés: {list(data3.keys())[:10]}")
                
                for key in ['participants', 'performances', 'chevaux', 'partants']:
                    if key in data3:
                        part = data3[key]
                        test3["analysis"].append(f"✓ Trouvé sous '{key}'")
                        
                        if isinstance(part, list) and len(part) > 0:
                            first = part[0]
                            if isinstance(first, dict):
                                test3["analysis"].append(f"✅ UTILISABLE")
                                test3["result"] = "SUCCESS"
                            break
    except Exception as e:
        test3["analysis"].append(f"❌ Erreur: {str(e)}")
        test3["result"] = "ERROR"
    
    results["tests"].append(test3)
    
    # Recommandation finale
    success_tests = [t for t in results["tests"] if t.get("result") == "SUCCESS"]
    if success_tests:
        results["recommendation"] = f"✅ Utiliser: {success_tests[0]['name']}"
        results["recommended_url"] = success_tests[0]["url"]
    else:
        results["recommendation"] = "❌ Aucun endpoint ne fonctionne correctement"
    
    return jsonify(results)


@app.route('/metrics')
def metrics():
    """
    Endpoint métriques Prometheus.
    
    Returns:
        Métriques au format Prometheus
    """
    if not PROMETHEUS_AVAILABLE:
        return jsonify({
            "error": "Prometheus client non installé",
            "install": "pip install prometheus-client"
        }), 501
    
    return Response(generate_latest(), mimetype='text/plain')


@app.route('/race', methods=['GET'])
def analyze_race():
    """
    Analyse une course et génère recommandations paris.
    
    Query params:
        date: DDMMYYYY (ex: 15122025)
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
                "usage": "/race?date=15122025&r=1&c=4&budget=20"
            }), 400
        
        if budget not in [5, 10, 15, 20]:
            return jsonify({
                "error": "Budget invalide (5|10|15|20)"
            }), 400
        
        logger.info(f"📊 Analyse course: {date_str} R{reunion}C{course} (Budget: {budget}€)")
        
        # === PHASE 1: PYTHON CALCULS ===
        
        # 1. Scraping données PMU
        logger.info("1️⃣ Scraping PMU...")
        race = scraper.get_race_data(date_str, reunion, course)
        
        if not race:
            return jsonify({
                "error": "Course introuvable ou données indisponibles"
            }), 404
        
        # Logs détaillés des données scrapées
        logger.info(f"✓ Scraping OK: {race.hippodrome} - {len(race.horses)} chevaux")
        logger.info(f"   Distance: {race.distance}m - Confiance: {race.confiance_globale}/10")
        if len(race.horses) > 0:
            horse_sample = race.horses[0]
            logger.info(f"   Exemple cheval: {horse_sample.nom} (#{horse_sample.numero})")
            logger.info(f"   - Musique: {horse_sample.musique[:20] if horse_sample.musique else 'N/A'}...")
            logger.info(f"   - Stats: {horse_sample.victoires}V/{horse_sample.courses}C")
            logger.info(f"   - Cote: {horse_sample.cote_probable}")
        else:
            logger.warning("⚠️ Aucun partant trouvé !")
        
        # 2. Scoring chevaux
        logger.info("2️⃣ Scoring chevaux...")
        race = scoring_engine.score_race(race)
        
        # 3. Détection Value Bets
        logger.info("3️⃣ Détection Value Bets...")
        race = value_detector.detect_value_bets(race)
        
        # === PHASE 2: GEMINI DÉCISIONS ===
        
        # 4. Construction prompt
        logger.info("4️⃣ Construction prompt...")
        full_prompt = prompt_builder.build_prompt(race, budget=budget)
        
        # 5. Appel Gemini
        logger.info("5️⃣ Appel Gemini API...")
        gemini_response = gemini_client.analyze_race(full_prompt)
        
        if not gemini_response:
            return jsonify({
                "error": "Erreur appel Gemini",
                "fallback": "Python-only analysis available"
            }), 500
        
        # 6. Validation + Budget Lock
        logger.info("6️⃣ Validation réponse...")
        analysis = response_validator.validate_and_parse(
            gemini_response, race, budget
        )
        
        if not analysis:
            return jsonify({
                "error": "Validation réponse échouée"
            }), 500
        
        # === PHASE 3: STOCKAGE & RÉPONSE ===
        
        # Métriques
        if PROMETHEUS_AVAILABLE:
            RACE_ANALYSES.inc()
        
        # 7. Stockage historique
        history_entry = {
            "date": date_str,
            "reunion": reunion,
            "course": course,
            "hippodrome": race.hippodrome,
            "budget": budget,
            "scenario": analysis.scenario_course,
            "nb_paris": len(analysis.paris_recommandes),
            "roi_attendu": analysis.roi_moyen_attendu,
            "timestamp": datetime.now().isoformat()
        }
        history_store.append(history_entry)
        
        # Sauvegarde historique persistant
        save_history(history_store)
        
        # Sauvegarde JSON détaillé (optionnel)
        _save_analysis_to_file(date_str, reunion, course, analysis)
        
        logger.info(
            f"✅ Analyse terminée: {analysis.scenario_course}",
            extra={
                'date': date_str,
                'reunion': reunion,
                'course': course,
                'hippodrome': race.hippodrome,
                'scenario': analysis.scenario_course,
                'nb_paris': len(analysis.paris_recommandes),
                'budget': budget
            }
        )
        
        # 8. Réponse JSON
        return jsonify(analysis.to_dict()), 200
    
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
    
    Returns:
        JSON avec analyse performance
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
        
        # Récupération résultats réels
        results = scraper.get_race_results(date_str, reunion, course)
        
        if not results:
            return jsonify({
                "error": "Résultats non disponibles (course non terminée ?)"
            }), 404
        
        # Chargement analyse initiale (depuis historique ou fichier)
        analysis = _load_analysis_from_file(date_str, reunion, course)
        
        if not analysis:
            return jsonify({
                "error": "Analyse initiale introuvable",
                "info": "Analysez d'abord la course via /race"
            }), 404
        
        # Calcul performance
        debrief = _calculate_debrief(analysis, results, date_str, reunion, course)
        
        logger.info(f"✅ Débriefing terminé: ROI réel {debrief.roi_reel}x")
        
        return jsonify(debrief.to_dict()), 200
    
    except Exception as e:
        logger.error(f"❌ Erreur débriefing: {e}")
        return jsonify({
            "error": "Erreur serveur",
            "detail": str(e)
        }), 500


@app.route('/history', methods=['GET'])
def get_history():
    """
    Retourne l'historique des courses analysées.
    
    Query params:
        limit: Nombre max résultats (défaut=50)
    
    Returns:
        JSON avec liste historique
    """
    try:
        limit = request.args.get('limit', default=50, type=int)
        
        # Tri par date décroissante
        sorted_history = sorted(
            history_store,
            key=lambda x: x['timestamp'],
            reverse=True
        )
        
        return jsonify({
            "total": len(sorted_history),
            "history": sorted_history[:limit]
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erreur historique: {e}")
        return jsonify({
            "error": "Erreur serveur"
        }), 500


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def _save_analysis_to_file(date_str: str, reunion: int, course: int,
                           analysis: RaceAnalysis):
    """Sauvegarde l'analyse dans un fichier JSON."""
    try:
        # Création dossier data/history si besoin
        history_dir = os.path.join(
            os.path.dirname(__file__),
            'data',
            'history'
        )
        os.makedirs(history_dir, exist_ok=True)
        
        # Nom fichier
        filename = f"{date_str}_R{reunion}C{course}_analysis.json"
        filepath = os.path.join(history_dir, filename)
        
        # Sauvegarde
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(analysis.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Analyse sauvegardée: {filename}")
    
    except Exception as e:
        logger.warning(f"Erreur sauvegarde analyse: {e}")


def _load_analysis_from_file(date_str: str, reunion: int,
                             course: int) -> Optional[dict]:
    """Charge une analyse depuis un fichier JSON."""
    try:
        filename = f"{date_str}_R{reunion}C{course}_analysis.json"
        filepath = os.path.join(
            os.path.dirname(__file__),
            'data',
            'history',
            filename
        )
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error(f"Erreur chargement analyse: {e}")
        return None


def _calculate_debrief(analysis: dict, results: dict, date_str: str,
                      reunion: int, course: int) -> Debrief:
    """
    Calcule le débriefing de performance avec vrais rapports PMU.
    
    Args:
        analysis: Analyse initiale avec paris recommandés
        results: Résultats réels avec arrivée et rapports PMU
        date_str, reunion, course: Identifiants course
    
    Returns:
        Debrief avec ROI réel calculé
    """
    
    # Extraction données
    arrivee = results['arrivee']
    non_partants = results['non_partants']
    rapports_pmu = results.get('rapports', {})
    paris_joues = analysis['paris_recommandes']
    top_5_predit = [h['numero'] for h in analysis['top_5_chevaux']]
    
    # Calcul précision top 3
    top_3_predit = top_5_predit[:3]
    top_3_reel = arrivee[:3] if len(arrivee) >= 3 else arrivee
    
    matches = sum(1 for num in top_3_predit if num in top_3_reel)
    precision_top_3 = (matches / 3) * 100 if len(top_3_reel) >= 3 else 0.0
    
    # Calcul gains avec VRAIS rapports PMU
    gains_total = 0.0
    mise_totale = sum(p['mise'] for p in paris_joues)
    paris_gagnants = []
    paris_details = []
    
    for pari in paris_joues:
        pari_detail = {
            'type': pari['type'],
            'chevaux': pari['chevaux'],
            'mise': pari['mise'],
            'gagnant': False,
            'gain': 0.0,
            'roi': 0.0
        }
        
        if _is_bet_winning(pari, arrivee):
            # Récupération rapport réel PMU
            rapport_reel = _get_rapport_pmu(pari, rapports_pmu, arrivee)
            
            if rapport_reel and rapport_reel > 0:
                # Calcul gain réel
                gain = pari['mise'] * (rapport_reel / 10)  # Rapports PMU sur base 10€
                gains_total += gain
                
                pari_detail['gagnant'] = True
                pari_detail['gain'] = round(gain, 2)
                pari_detail['roi'] = round(rapport_reel / 10, 2)
                
                paris_gagnants.append({
                    'type': pari['type'],
                    'gain': gain,
                    'rapport': rapport_reel
                })
            else:
                # Pari gagnant mais rapport non disponible
                # Utiliser estimation
                gain_estime = pari['mise'] * pari.get('roi_attendu', 2.0)
                gains_total += gain_estime
                
                pari_detail['gagnant'] = True
                pari_detail['gain'] = round(gain_estime, 2)
                pari_detail['roi'] = pari.get('roi_attendu', 2.0)
                
                paris_gagnants.append({
                    'type': pari['type'],
                    'gain': gain_estime,
                    'rapport': 'estimé'
                })
                
                logger.warning(f"Rapport PMU manquant pour {pari['type']}, utilisation estimation")
        
        paris_details.append(pari_detail)
    
    # ROI réel
    roi_reel = gains_total / mise_totale if mise_totale > 0 else 0.0
    
    # Commentaire contextualisé
    if roi_reel >= 2.0:
        commentaire = f"🎉 Excellent! ROI {roi_reel:.1f}x. {len(paris_gagnants)} paris gagnants."
    elif roi_reel >= 1.0:
        commentaire = f"✅ Profitable! ROI {roi_reel:.1f}x. Stratégie gagnante."
    elif roi_reel >= 0.5:
        commentaire = f"⚠️ Perte limitée. ROI {roi_reel:.1f}x. À améliorer."
    else:
        commentaire = f"❌ Perte importante. ROI {roi_reel:.1f}x. Arrivée difficile."
    
    # Ajout info précision
    if precision_top_3 >= 66:
        commentaire += f" Top 3 bien anticipé ({precision_top_3:.0f}%)."
    elif precision_top_3 >= 33:
        commentaire += f" Quelques chevaux placés ({precision_top_3:.0f}%)."
    else:
        commentaire += f" Arrivée surprenante ({precision_top_3:.0f}%)."
    
    debrief = Debrief(
        date=date_str,
        reunion=reunion,
        course=course,
        hippodrome=analysis.get('hippodrome', 'INCONNU'),
        arrivee=arrivee,
        non_partants=non_partants,
        paris_joues=paris_details,
        paris_gagnants=[p['type'] for p in paris_gagnants],
        gains_total=round(gains_total, 2),
        mise_totale=mise_totale,
        roi_reel=round(roi_reel, 2),
        top_5_predit=top_5_predit,
        top_5_reel=arrivee[:5],
        precision_top_3=round(precision_top_3, 1),
        commentaire=commentaire
    )
    
    return debrief


def _get_rapport_pmu(pari: dict, rapports_pmu: dict, arrivee: List[int]) -> Optional[float]:
    """
    Récupère le rapport PMU réel pour un pari donné.
    
    Args:
        pari: Pari joué avec type et chevaux
        rapports_pmu: Rapports officiels PMU
        arrivee: Ordre d'arrivée
    
    Returns:
        Rapport PMU (base 10€) ou None si indisponible
    """
    type_pari = pari['type']
    chevaux = pari['chevaux']
    
    try:
        if type_pari == 'SIMPLE_GAGNANT':
            # Rapport simple gagnant pour le cheval
            rapports_simple = rapports_pmu.get('rapportSimpleGagnant', [])
            for r in rapports_simple:
                if r.get('numero') == chevaux[0]:
                    return r.get('rapport', 0.0)
        
        elif type_pari == 'SIMPLE_PLACE':
            # Rapport simple placé
            rapports_place = rapports_pmu.get('rapportSimplePlace', [])
            for r in rapports_place:
                if r.get('numero') == chevaux[0]:
                    return r.get('rapport', 0.0)
        
        elif type_pari == 'COUPLE_GAGNANT':
            # Rapport couple gagnant
            couple = rapports_pmu.get('rapportCoupleGagnant', {})
            # Vérifier si ordre correspond
            if couple.get('numeros') == chevaux[:2]:
                return couple.get('rapport', 0.0)
        
        elif type_pari == 'COUPLE_PLACE':
            # Rapport couple placé
            couples_place = rapports_pmu.get('rapportCouplePlace', [])
            for c in couples_place:
                if set(c.get('numeros', [])) == set(chevaux[:2]):
                    return c.get('rapport', 0.0)
        
        elif type_pari == 'TRIO':
            # Rapport trio
            trio = rapports_pmu.get('rapportTrio', {})
            if set(trio.get('numeros', [])) == set(chevaux[:3]):
                return trio.get('rapport', 0.0)
        
        elif type_pari in ['MULTI_EN_4', 'MULTI_EN_5']:
            # Rapport multi
            multi = rapports_pmu.get('rapportMulti', {})
            return multi.get('rapport', 0.0)
        
        elif type_pari == 'DEUX_SUR_QUATRE':
            # Rapport 2sur4
            deux_sur_4 = rapports_pmu.get('rapportDeuxSurQuatre', {})
            return deux_sur_4.get('rapport', 0.0)
    
    except (KeyError, TypeError, AttributeError) as e:
        logger.debug(f"Erreur extraction rapport {type_pari}: {e}")
    
    return None


def _is_bet_winning(pari: dict, arrivee: List[int]) -> bool:
    """Vérifie si un pari est gagnant (logique simplifiée)."""
    chevaux = pari['chevaux']
    type_pari = pari['type']
    
    if type_pari == 'SIMPLE_GAGNANT':
        return chevaux[0] == arrivee[0]
    
    elif type_pari == 'SIMPLE_PLACE':
        return chevaux[0] in arrivee[:3]
    
    elif type_pari == 'COUPLE_GAGNANT':
        return chevaux[0] == arrivee[0] and chevaux[1] == arrivee[1]
    
    elif type_pari == 'COUPLE_PLACE':
        return chevaux[0] in arrivee[:3] and chevaux[1] in arrivee[:3]
    
    elif type_pari == 'TRIO':
        return all(c in arrivee[:3] for c in chevaux)
    
    elif type_pari in ['MULTI_EN_4', 'MULTI_EN_5']:
        # Au moins 2 chevaux dans top 4
        return sum(1 for c in chevaux if c in arrivee[:4]) >= 2
    
    elif type_pari == 'DEUX_SUR_QUATRE':
        return sum(1 for c in chevaux if c in arrivee[:4]) >= 2
    
    return False


# ============================================================================
# DÉMARRAGE SERVEUR
# ============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
