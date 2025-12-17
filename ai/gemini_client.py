# ============================================================================
# TROT SYSTEM v8.0 - CLIENT GEMINI (SUPPORT DUAL API KEY)
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
    """Client pour l'API Google Gemini - Support GEMINI_API_KEY et GOOGLE_API_KEY."""
    
    MODEL_NAMES = [
        "gemini-flash-latest",
        "gemini-2.5-flash", 
        "gemini-2.0-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-pro-latest",
        "gemini-2.5-pro",
        "gemini-pro",
    ]
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le client Gemini.
        Support GEMINI_API_KEY OU GOOGLE_API_KEY.
        
        Args:
            api_key: Clé API Google (ou env var)
        """
        # Support des deux noms de variables !
        self.api_key = (
            api_key or 
            os.environ.get("GEMINI_API_KEY") or 
            os.environ.get("GOOGLE_API_KEY")
        )
        
        if not self.api_key:
            raise ValueError(
                "API Key manquante ! "
                "Définir GEMINI_API_KEY ou GOOGLE_API_KEY en variable d'environnement"
            )
        
        # Log quel nom de variable est utilisé
        if os.environ.get("GEMINI_API_KEY"):
            logger.info("Using GEMINI_API_KEY")
        elif os.environ.get("GOOGLE_API_KEY"):
            logger.info("Using GOOGLE_API_KEY")
        
        # Configuration API
        genai.configure(api_key=self.api_key)
        
        self.model = None
        self.model_name = None
        
        logger.info("Initialisation Gemini client...")
        
        # Essayer chaque modèle
        for model_name in self.MODEL_NAMES:
            try:
                logger.info(f"Test modèle: {model_name}")
                
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
                
                # Test direct
                response = test_model.generate_content(
                    '{"status": "test"}',
                    request_options={"timeout": 15}
                )
                
                if response and response.text:
                    self.model = test_model
                    self.model_name = model_name
                    logger.info(f"✓ Modèle fonctionnel: {model_name}")
                    break
                
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"✗ Modèle {model_name}: {error_msg[:100]}")
                
                if "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg:
                    raise ValueError(
                        "API Key invalide ! "
                        "Vérifiez GEMINI_API_KEY ou GOOGLE_API_KEY sur Render. "
                        "Créez une nouvelle clé sur https://aistudio.google.com/apikey"
                    )
                
                continue
        
        if not self.model:
            raise ValueError(
                f"Aucun modèle Gemini accessible ! "
                f"Modèles testés: {self.MODEL_NAMES}. "
                f"Vérifiez votre API Key."
            )
        
        logger.info(f"✓ Client Gemini OK (modèle: {self.model_name})")
    
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
            
            response = self.model.generate_content(
                full_prompt,
                request_options={"timeout": 60}
            )
            
            if not response or not response.text:
                logger.error("Réponse Gemini vide")
                return None
            
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
            raise
    
    def test_connection(self) -> bool:
        """Test rapide de connexion à l'API."""
        try:
            test_prompt = "Réponds simplement 'OK' en JSON: {\"status\": \"OK\"}"
            response = self.model.generate_content(
                test_prompt,
                request_options={"timeout": 15}
            )
            
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
    print("TROT SYSTEM v8.0 - TEST CLIENT GEMINI (DUAL API KEY SUPPORT)")
    print("=" * 70)
    
    print("\n1. Test initialisation")
    try:
        client = GeminiClient()
        print(f"   ✓ Client OK avec modèle: {client.model_name}")
    except ValueError as e:
        print(f"   ✗ Erreur: {e}")
        exit(1)
    
    print("\n2. Test connexion API")
    if client.test_connection():
        print("   ✓ Connexion OK")
    else:
        print("   ✗ Connexion échouée")
    
    print("\n3. Test requête JSON")
    result = client.analyze_race('{"test": "OK"}')
    if result:
        print(f"   ✓ Réponse: {result}")
    else:
        print("   ✗ Pas de réponse")
    
    print("\n" + "=" * 70)
    print(f"SUCCESS! Modèle: {client.model_name}")
    print("=" * 70)
