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
    
    def build_prompt(self, race: Race, budget: float = 20.0, max_horses: int = 10) -> str:
        """
        Construit le prompt complet XML optimisé.
        
        Args:
            race: Course avec scores calculés
            budget: Budget disponible (€)
            max_horses: Nombre max de chevaux à inclure (défaut 10)
        
        Returns:
            Prompt XML complet optimisé
        """
        logger.info(f"Construction prompt pour {race.hippodrome} R{race.reunion}C{race.course}")
        
        # Filtrer top N chevaux pour réduire tokens
        horses_to_include = race.horses[:max_horses] if len(race.horses) > max_horses else race.horses
        
        if len(race.horses) > max_horses:
            logger.info(f"Optimisation prompt: {max_horses}/{len(race.horses)} chevaux inclus")
        
        # Remplacement variables dans system prompt
        prompt = self.system_prompt.format(
            hippodrome=race.hippodrome,
            reunion=race.reunion,
            course=race.course,
            distance=race.distance,
            discipline=race.discipline,
            type_depart=race.type_depart,
            montantPrix=race.montant_prix,
            nb_partants=len(horses_to_include),  # Ajusté
            etat_piste=race.etat_piste,
            impact_piste=race.impact_piste or "Normal",
            confiance_globale=race.confiance_globale,
            quality_score=race.qualite_donnees,
            missing_data_pct=race.donnees_manquantes_pct,
            budget=budget
        )
        
        # Injection scores chevaux (optimisés)
        horses_xml = self._build_horses_xml_optimized(horses_to_include)
        prompt = prompt.replace("<!-- HORSES_XML_PLACEHOLDER -->", horses_xml)
        
        # Estimation tokens
        tokens_approx = len(prompt) // 4
        logger.info(f"✓ Prompt construit ({len(prompt)} caractères, ~{tokens_approx} tokens)")
        
        return prompt
    
    def _build_horses_xml_optimized(self, horses: list) -> str:
        """
        Génère le XML des chevaux de manière optimisée.
        
        Optimisations:
        - Résume musique (5 dernières courses max)
        - Format compact
        """
        xml_parts = []
        
        for horse in horses:
            # Résumer musique si trop longue
            musique_short = horse.musique[:5] if len(horse.musique) > 5 else horse.musique
            
            # XML compact (une seule ligne par cheval)
            xml = (
                f'<horse num="{horse.numero}" nom="{horse.nom}" '
                f'score="{horse.score_total}" cote="{horse.cote}" '
                f'driver="{horse.driver}" entraineur="{horse.entraineur}" '
                f'musique="{musique_short}" '
                f'courses="{horse.nb_courses}" victoires="{horse.nb_victoires}" '
                f'places="{horse.nb_places}" gains="{horse.gains_carriere}" '
                f'avis="{horse.avis_entraineur}" deferre="{horse.deferre}" '
                f'value_bet="{horse.is_value_bet}" edge="{horse.edge_percent}" />'
            )
            xml_parts.append(xml)
        
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
