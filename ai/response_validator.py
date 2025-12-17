# ============================================================================
# TROT SYSTEM v8.0 - VALIDATEUR RÉPONSE GEMINI
# ============================================================================

from models.bet import BetRecommendation, RaceAnalysis
from models.race import Race
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

class ResponseValidator:
    """Valide et sécurise les réponses Gemini."""
    
    def __init__(self):
        self.required_fields = [
            'scenario_course',
            'analyse_tactique',
            'top_5_chevaux',
            'value_bets_detectes',
            'paris_recommandes',
            'budget_total',
            'budget_utilise',
            'roi_moyen_attendu',
            'conseil_final',
            'confiance_globale'
        ]
        
        self.valid_scenarios = [
            'CADENAS', 'BATAILLE', 'SURPRISE', 'PIEGE', 'NON_JOUABLE'
        ]
        
        self.valid_bet_types = [
            'SIMPLE_GAGNANT', 'SIMPLE_PLACE',
            'COUPLE_GAGNANT', 'COUPLE_PLACE',
            'TRIO', 'MULTI_EN_4', 'MULTI_EN_5', 'DEUX_SUR_QUATRE'
        ]
    
    def validate_and_parse(self, gemini_response: Dict, race: Race,
                          budget: float, tolerance: float = 0.50) -> Optional[RaceAnalysis]:
        """
        Valide la réponse Gemini et crée un objet RaceAnalysis.
        
        Args:
            gemini_response: Réponse JSON Gemini
            race: Course analysée
            budget: Budget max
            tolerance: Tolérance budget (€)
        
        Returns:
            RaceAnalysis ou None si validation échoue
        """
        logger.info("Validation réponse Gemini...")
        
        # 1. Validation structure
        if not self._validate_structure(gemini_response):
            return None
        
        # 2. Validation scénario
        if not self._validate_scenario(gemini_response):
            return None
        
        # 3. Validation budget (CRITIQUE)
        budget_ok, budget_msg = self._validate_budget(
            gemini_response, budget, tolerance
        )
        if not budget_ok:
            logger.error(f"❌ Budget Lock: {budget_msg}")
            # Correction automatique
            gemini_response = self._enforce_budget(gemini_response, budget, tolerance)
        
        # 4. Kill Switch confiance faible (seuil baissé 6→4 pour moins de rejets)
        confiance = gemini_response.get('confiance_globale', 0)
        logger.info(f"Confiance Gemini: {confiance}/10")
        
        if confiance < 4:  # Seuil abaissé de 6 à 4
            logger.warning(f"⚠️ Kill Switch: Confiance globale {confiance} < 4/10")
            return self._create_non_jouable_response(race, budget, 
                                                     "Confiance données insuffisante")
        elif confiance < 6:
            logger.warning(f"⚠️ Confiance faible ({confiance}/10) mais analyse acceptée")
        
        # 5. Validation paris
        if not self._validate_bets(gemini_response, race):
            return None
        
        # 6. Construction RaceAnalysis
        try:
            analysis = self._parse_to_race_analysis(gemini_response, race)
            logger.info("✓ Réponse validée et parsée")
            return analysis
        
        except Exception as e:
            logger.error(f"Erreur parse RaceAnalysis: {e}")
            return None
    
    def _validate_structure(self, response: Dict) -> bool:
        """Vérifie que tous les champs requis sont présents."""
        for field in self.required_fields:
            if field not in response:
                logger.error(f"Champ manquant: {field}")
                return False
        return True
    
    def _validate_scenario(self, response: Dict) -> bool:
        """Vérifie que le scénario est valide."""
        scenario = response.get('scenario_course')
        if scenario not in self.valid_scenarios:
            logger.error(f"Scénario invalide: {scenario}")
            return False
        return True
    
    def _validate_budget(self, response: Dict, budget: float,
                        tolerance: float) -> tuple[bool, str]:
        """
        Validation budget (Budget Lock).
        
        Returns:
            (is_valid, message)
        """
        budget_utilise = response.get('budget_utilise', 0)
        
        if budget_utilise > budget + tolerance:
            return False, f"Dépassement: {budget_utilise}€ > {budget + tolerance}€"
        
        # Vérification paris non vides (sauf NON_JOUABLE)
        if response.get('scenario_course') != 'NON_JOUABLE':
            if not response.get('paris_recommandes'):
                return False, "Aucun pari pour course jouable"
        
        return True, "Budget OK"
    
    def _enforce_budget(self, response: Dict, budget: float,
                       tolerance: float) -> Dict:
        """
        Force le respect du budget en ajustant les mises.
        
        Returns:
            Response corrigée
        """
        logger.warning("⚙️ Correction budget automatique...")
        
        paris = response.get('paris_recommandes', [])
        if not paris:
            return response
        
        # Calcul total actuel
        total_actuel = sum(p.get('mise', 0) for p in paris)
        
        # Protection division par zéro
        if total_actuel <= 0:
            logger.warning("⚠️ Total paris = 0, impossible d'ajuster budget")
            return response
        
        max_budget = budget + tolerance
        
        # Ratio réduction
        ratio = max_budget / total_actuel
        
        # Ajustement mises
        for pari in paris:
            pari['mise'] = round(pari['mise'] * ratio, 2)
        
        # Recalcul total
        response['budget_utilise'] = sum(p['mise'] for p in paris)
        
        logger.info(f"✓ Budget corrigé: {response['budget_utilise']}€")
        
        return response
    
    def _validate_bets(self, response: Dict, race: Race) -> bool:
        """Valide les paris recommandés."""
        paris = response.get('paris_recommandes', [])
        
        for pari in paris:
            # Type valide
            if pari.get('type') not in self.valid_bet_types:
                logger.error(f"Type pari invalide: {pari.get('type')}")
                return False
            
            # Chevaux valides
            chevaux = pari.get('chevaux', [])
            for num in chevaux:
                if num < 1 or num > race.nb_partants:
                    logger.error(f"Numéro cheval invalide: {num}")
                    return False
        
        return True
    
    def _parse_to_race_analysis(self, response: Dict, race: Race) -> RaceAnalysis:
        """Convertit la réponse validée en RaceAnalysis."""
        
        # Parse paris
        bets = []
        for pari_data in response.get('paris_recommandes', []):
            bet = BetRecommendation(
                type=pari_data['type'],
                chevaux=pari_data['chevaux'],
                chevaux_noms=pari_data['chevaux_noms'],
                mise=pari_data['mise'],
                roi_attendu=pari_data['roi_attendu'],
                justification=pari_data['justification']
            )
            bets.append(bet)
        
        # Construction RaceAnalysis
        analysis = RaceAnalysis(
            scenario_course=response['scenario_course'],
            analyse_tactique=response['analyse_tactique'],
            top_5_chevaux=response['top_5_chevaux'],
            value_bets_detectes=response['value_bets_detectes'],
            paris_recommandes=bets,
            budget_total=response['budget_total'],
            budget_utilise=response['budget_utilise'],
            roi_moyen_attendu=response['roi_moyen_attendu'],
            conseil_final=response['conseil_final'],
            confiance_globale=response['confiance_globale']
        )
        
        return analysis
    
    def _create_non_jouable_response(self, race: Race, budget: float,
                                    reason: str) -> RaceAnalysis:
        """Crée une réponse NON_JOUABLE par sécurité."""
        logger.info(f"Génération réponse NON_JOUABLE: {reason}")
        
        return RaceAnalysis(
            scenario_course="NON_JOUABLE",
            analyse_tactique=f"Course non jouable: {reason}",
            top_5_chevaux=[],
            value_bets_detectes=[],
            paris_recommandes=[],
            budget_total=budget,
            budget_utilise=0.0,
            roi_moyen_attendu=0.0,
            conseil_final=f"Abstention recommandée ({reason})",
            confiance_globale=race.confiance_globale
        )


# ============================================================================
# VALIDATION MODULE
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("TROT SYSTEM v8.0 - TEST RESPONSE VALIDATOR")
    print("=" * 70)
    
    # Mock réponse Gemini
    test_response = {
        "scenario_course": "CADENAS",
        "analyse_tactique": "Test analyse",
        "top_5_chevaux": [],
        "value_bets_detectes": [],
        "paris_recommandes": [
            {
                "type": "SIMPLE_GAGNANT",
                "chevaux": [7],
                "chevaux_noms": ["LASLO"],
                "mise": 8.0,
                "roi_attendu": 3.1,
                "justification": "Test"
            }
        ],
        "budget_total": 20.0,
        "budget_utilise": 8.0,
        "roi_moyen_attendu": 3.1,
        "conseil_final": "Test",
        "confiance_globale": 9
    }
    
    # Test validation
    validator = ResponseValidator()
    
    print("\n1. Test validation structure")
    if validator._validate_structure(test_response):
        print("   ✓ Structure OK")
    
    print("\n2. Test validation scénario")
    if validator._validate_scenario(test_response):
        print("   ✓ Scénario OK")
    
    print("\n3. Test validation budget")
    ok, msg = validator._validate_budget(test_response, 20.0, 0.50)
    print(f"   {'✓' if ok else '✗'} Budget: {msg}")
    
    print("\n" + "=" * 70)
