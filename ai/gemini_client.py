# ============================================================================
# TROT SYSTEM v8.0 - CLIENT GEMINI FLASH 1.5
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
    """Client pour l'API Google Gemini Flash 1.5."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le client Gemini.
        
        Args:
            api_key: Clé API Google (ou env var GEMINI_API_KEY)
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY manquante (env var ou paramètre)")
        
        # Configuration API
        genai.configure(api_key=self.api_key)
        
        # Modèle + paramètres
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-002",
            generation_config={
                "temperature": 0.4,        # Équilibre créativité/déterminisme
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
                "response_mime_type": "application/json"  # 🔥 Force JSON pur
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        logger.info("✓ Client Gemini Flash 1.5 initialisé")
    
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
            logger.info("Appel Gemini API...")
            
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
    print("TROT SYSTEM v8.0 - TEST CLIENT GEMINI")
    print("=" * 70)
    
    # Test 1: Initialisation
    print("\n1. Test initialisation client")
    try:
        client = GeminiClient()
        print("   ✓ Client initialisé")
    except ValueError as e:
        print(f"   ✗ Erreur: {e}")
        print("   → Définir GEMINI_API_KEY en variable d'environnement")
        exit(1)
    
    # Test 2: Connexion
    print("\n2. Test connexion API")
    if client.test_connection():
        print("   ✓ Connexion Gemini OK")
    else:
        print("   ✗ Connexion échouée")
    
    # Test 3: Requête simple
    print("\n3. Test requête JSON")
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
