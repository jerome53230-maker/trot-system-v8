# ============================================================================
# TROT SYSTEM v8.0 - CLIENT GEMINI (VERSION ROBUSTE)
# ============================================================================

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from tenacity import retry, stop_after_attempt, wait_exponential
import json
import logging
import os
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class GeminiClient:
    """Client pour l'API Google Gemini avec fallback multi-modèles."""
    
    # Liste des noms de modèles à tester (ordre de préférence)
    MODEL_NAMES = [
        "gemini-1.5-flash-8b",          # Dernier modèle Flash (décembre 2024)
        "gemini-1.5-flash-002",         # Version stable spécifique
        "gemini-1.5-flash-latest",      # Latest explicite
        "gemini-1.5-flash",             # Nom original (fallback)
        "gemini-pro",                   # Fallback Pro (plus cher)
    ]
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le client Gemini avec détection automatique du modèle.
        
        Args:
            api_key: Clé API Google (ou env var GEMINI_API_KEY)
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY manquante (env var ou paramètre)")
        
        # Configuration API
        genai.configure(api_key=self.api_key)
        
        # Tentative de trouver un modèle qui fonctionne
        self.model = None
        self.model_name = None
        
        for model_name in self.MODEL_NAMES:
            try:
                logger.info(f"Tentative modèle: {model_name}")
                
                # Créer modèle de test
                test_model = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config={
                        "temperature": 0.4,
                        "top_p": 0.95,
                        "top_k": 40,
                        "max_output_tokens": 8192,
                        "response_mime_type": "application/json"
                    },
                    safety_settings={
                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    }
                )
                
                # Test rapide
                response = test_model.generate_content("Test")
                
                # Si on arrive ici, le modèle fonctionne !
                self.model = test_model
                self.model_name = model_name
                logger.info(f"✓ Modèle fonctionnel trouvé: {model_name}")
                break
                
            except Exception as e:
                logger.warning(f"✗ Modèle {model_name} non disponible: {e}")
                continue
        
        if not self.model:
            # Lister modèles disponibles
            available = self._list_available_models()
            raise ValueError(
                f"Aucun modèle Gemini disponible ! "
                f"Modèles testés: {self.MODEL_NAMES}. "
                f"Modèles disponibles: {available}"
            )
        
        logger.info(f"✓ Client Gemini initialisé (modèle: {self.model_name})")
    
    def _list_available_models(self) -> list:
        """Liste les modèles disponibles pour cette API key."""
        try:
            models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    models.append(m.name)
            return models
        except Exception as e:
            logger.error(f"Impossible de lister modèles: {e}")
            return []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def analyze_race(self, full_prompt: str) -> Optional[Dict]:
        """
        Envoie le prompt complet à Gemini et récupère la réponse JSON.
        
        Args:
            full_prompt: Prompt XML complet (système + race data)
        
        Returns:
            Dict JSON ou None si échec
        """
        try:
            logger.info(f"Appel Gemini API (modèle: {self.model_name})...")
            
            response = self.model.generate_content(full_prompt)
            
            # Extraction texte
            if not response or not response.text:
                logger.error("Réponse Gemini vide")
                return None
            
            # Parse JSON
            try:
                result = json.loads(response.text)
                logger.info("✓ Réponse Gemini reçue et parsée")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Erreur parse JSON: {e}")
                logger.error(f"Réponse brute: {response.text[:500]}")
                return None
        
        except Exception as e:
            logger.error(f"Erreur appel Gemini: {e}")
            raise  # Reraise pour retry tenacity
    
    def test_connection(self) -> bool:
        """
        Test rapide de connexion à l'API.
        
        Returns:
            True si connexion OK
        """
        try:
            test_prompt = "Réponds simplement 'OK' en JSON: {\"status\": \"OK\"}"
            response = self.model.generate_content(test_prompt)
            
            if response and response.text:
                data = json.loads(response.text)
                return data.get("status") == "OK"
            
            return False
        
        except Exception as e:
            logger.error(f"Test connexion échoué: {e}")
            return False


# ============================================================================
# VALIDATION MODULE
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("TROT SYSTEM v8.0 - TEST CLIENT GEMINI (ROBUSTE)")
    print("=" * 70)
    
    # Test 1: Initialisation
    print("\n1. Test initialisation client (détection auto modèle)")
    try:
        client = GeminiClient()
        print(f"   ✓ Client initialisé avec modèle: {client.model_name}")
    except ValueError as e:
        print(f"   ✗ Erreur: {e}")
        exit(1)
    
    # Test 2: Liste modèles disponibles
    print("\n2. Modèles disponibles:")
    available = client._list_available_models()
    for model in available[:10]:  # Top 10
        print(f"   - {model}")
    
    # Test 3: Connexion
    print("\n3. Test connexion API")
    if client.test_connection():
        print("   ✓ Connexion Gemini OK")
    else:
        print("   ✗ Connexion échouée")
    
    # Test 4: Requête JSON
    print("\n4. Test requête JSON")
    simple_prompt = """Réponds en JSON avec:
{
    "test": "OK",
    "message": "Gemini fonctionne"
}"""
    
    result = client.analyze_race(simple_prompt)
    if result:
        print(f"   ✓ Réponse reçue: {result}")
    else:
        print("   ✗ Pas de réponse")
    
    print("\n" + "=" * 70)
