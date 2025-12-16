# ============================================================================
# TROT SYSTEM v8.0 - CONSTRUCTEUR PROMPT GEMINI
# ============================================================================

from models.race import Race
from typing import Dict
import logging
import os

logger = logging.getLogger(__name__)

class PromptBuilder:
    """Construit le prompt XML complet pour Gemini."""
    
    def __init__(self):
        # Chargement system prompt
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'prompts',
            'system_prompt_v8.txt'
        )
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.system_prompt = f.read()
        
        logger.info("✓ System prompt chargé")
    
    def build_prompt(self, race: Race, budget: float = 20.0) -> str:
        """
        Construit le prompt complet XML.
        
        Args:
            race: Course avec scores calculés
            budget: Budget disponible (€)
        
        Returns:
            Prompt XML complet
        """
        logger.info(f"Construction prompt pour {race.hippodrome} R{race.reunion}C{race.course}")
        
        # Remplacement variables dans system prompt
        prompt = self.system_prompt.format(
            hippodrome=race.hippodrome,
            reunion=race.reunion,
            course=race.course,
            distance=race.distance,
            discipline=race.discipline,
            type_depart=race.type_depart,
            montantPrix=race.montant_prix,
            nb_partants=race.nb_partants,
            etat_piste=race.etat_piste,
            impact_piste=race.impact_piste or "Normal",
            confiance_globale=race.confiance_globale,
            quality_score=race.qualite_donnees,
            missing_data_pct=race.donnees_manquantes_pct,
            budget=budget
        )
        
        # Injection scores chevaux
        horses_xml = self._build_horses_xml(race)
        prompt = prompt.replace("<!-- HORSES_XML_PLACEHOLDER -->", horses_xml)
        
        logger.info(f"✓ Prompt construit ({len(prompt)} caractères)")
        
        return prompt
    
    def _build_horses_xml(self, race: Race) -> str:
        """Génère le XML de tous les chevaux."""
        xml_parts = []
        
        for horse in race.horses:
            xml_parts.append(horse.to_xml())
        
        return "\n".join(xml_parts)
    
    def detect_scenario_hints(self, race: Race) -> str:
        """
        Détecte des indices de scénario pour aider Gemini.
        
        Returns:
            Hint textuel à ajouter au prompt
        """
        top_5 = race.get_top_horses(5)
        
        # CADENAS ?
        if len(top_5) >= 2:
            ecart = top_5[0].score_total - top_5[1].score_total
            if top_5[0].score_total >= 85 and ecart >= 10:
                return "HINT: Favori dominant détecté (scénario CADENAS probable)"
        
        # PIÈGE ?
        for horse in race.horses:
            if horse.is_favoris and horse.score_total < 65:
                return "HINT: Favori fragile détecté (scénario PIÈGE possible)"
        
        # BATAILLE ?
        chevaux_70plus = sum(1 for h in race.horses if h.score_total >= 70)
        if chevaux_70plus >= 5:
            return "HINT: Nombreux chevaux compétitifs (scénario BATAILLE)"
        
        # SURPRISE ?
        value_bets = race.get_value_bets()
        if value_bets and value_bets[0].edge_percent >= 15:
            return f"HINT: Value Bet détecté (#{value_bets[0].numero} edge {value_bets[0].edge_percent}%)"
        
        return ""


# ============================================================================
# VALIDATION MODULE
# ============================================================================

if __name__ == "__main__":
    from core.scraper import PMUScraper
    from core.scoring_engine import ScoringEngine
    from core.value_bet_detector import ValueBetDetector
    
    print("=" * 70)
    print("TROT SYSTEM v8.0 - TEST PROMPT BUILDER")
    print("=" * 70)
    
    # Préparation race
    print("\n1. Récupération course...")
    scraper = PMUScraper()
    race = scraper.get_race_data("15122025", 1, 4)
    
    if race:
        print(f"   ✓ Course récupérée: {race.hippodrome}")
        
        # Scoring
        print("\n2. Scoring...")
        engine = ScoringEngine()
        race = engine.score_race(race)
        print(f"   ✓ Scores calculés")
        
        # Value bets
        print("\n3. Détection Value Bets...")
        detector = ValueBetDetector()
        race = detector.detect_value_bets(race)
        print(f"   ✓ Value Bets analysés")
        
        # Construction prompt
        print("\n4. Construction prompt...")
        builder = PromptBuilder()
        prompt = builder.build_prompt(race, budget=20.0)
        
        print(f"   ✓ Prompt construit:")
        print(f"     Longueur: {len(prompt)} caractères")
        print(f"     Tokens estimés: ~{len(prompt) // 4}")
        
        # Hint scénario
        hint = builder.detect_scenario_hints(race)
        if hint:
            print(f"     {hint}")
        
        # Aperçu
        print("\n5. Aperçu prompt (200 premiers caractères):")
        print("   " + prompt[:200] + "...")
    
    print("\n" + "=" * 70)
