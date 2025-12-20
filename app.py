"""
TROT SYSTEM v8.0 - API FLASK MINIMALE STANDALONE
Version simplifiée sans dépendances externes
Compatible Python 3.13
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
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

# Configuration Gemini (optionnel)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Historique simple (JSON en mémoire)
history_store = []

# ============================================================================
# ENDPOINTS API
# ============================================================================

@app.route('/')
def home():
    """Page d'accueil avec documentation API."""
    return jsonify({
        "name": "Trot System v8.0 - Minimal",
        "version": "8.0.0-minimal",
        "description": "API Flask minimale pour système d'analyse hippique",
        "status": "operational",
        "endpoints": {
            "/": "GET - Cette page",
            "/health": "GET - Health check",
            "/test-gemini": "GET - Test connexion Gemini API",
            "/history": "GET - Historique des analyses"
        },
        "documentation": "Version minimale standalone sans dépendances externes"
    })


@app.route('/health')
def health():
    """
    Health check de l'application.
    
    Returns:
        JSON avec status de santé
    """
    try:
        # Test basique
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "python_version": "3.13+",
            "flask": "ok",
            "cors": "ok",
            "gemini_api_key": "configured" if GEMINI_API_KEY else "missing",
            "historique_entries": len(history_store)
        }
        
        # Test Gemini si clé disponible
        if GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                # Test simple
                response = model.generate_content("Test")
                health_status["gemini_api"] = "ok"
            except Exception as e:
                logger.warning(f"Gemini test failed: {e}")
                health_status["gemini_api"] = f"error: {str(e)}"
        else:
            health_status["gemini_api"] = "no_api_key"
        
        return jsonify(health_status), 200
    
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503


@app.route('/test-gemini')
def test_gemini():
    """
    Test de connexion à l'API Gemini.
    
    Returns:
        JSON avec résultat du test
    """
    if not GEMINI_API_KEY:
        return jsonify({
            "status": "error",
            "message": "GEMINI_API_KEY non configurée",
            "help": "Ajouter GEMINI_API_KEY dans Environment Variables sur Render"
        }), 400
    
    try:
        import google.generativeai as genai
        
        # Configuration
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Test simple
        test_prompt = "Réponds juste 'OK' si tu me reçois."
        response = model.generate_content(test_prompt)
        
        return jsonify({
            "status": "success",
            "message": "Connexion Gemini OK",
            "model": "gemini-2.0-flash-exp",
            "test_prompt": test_prompt,
            "response": response.text,
            "timestamp": datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Gemini test error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route('/history')
def get_history():
    """
    Retourne l'historique des analyses.
    
    Returns:
        JSON avec liste des analyses
    """
    return jsonify({
        "status": "success",
        "count": len(history_store),
        "history": history_store
    }), 200


@app.route('/add-test-entry', methods=['POST'])
def add_test_entry():
    """
    Ajoute une entrée de test dans l'historique.
    
    Returns:
        JSON avec confirmation
    """
    try:
        data = request.get_json() or {}
        
        entry = {
            "id": len(history_store) + 1,
            "timestamp": datetime.now().isoformat(),
            "type": "test",
            "data": data
        }
        
        history_store.append(entry)
        
        return jsonify({
            "status": "success",
            "message": "Entrée ajoutée",
            "entry": entry
        }), 201
    
    except Exception as e:
        logger.error(f"Add entry error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


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
        "available_endpoints": ["/", "/health", "/test-gemini", "/history"]
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
    logger.info(f"🚀 Démarrage Trot System v8.0 - Minimal sur port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
