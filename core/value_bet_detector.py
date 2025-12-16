# ============================================================================
# TROT SYSTEM v8.0 - DÉTECTEUR VALUE BETS
# ============================================================================

from models.race import Race, Horse
from typing import List
import logging

logger = logging.getLogger(__name__)

class ValueBetDetector:
    """Détecte les opportunités de paris à valeur (sous-cotés)."""
    
    def __init__(self):
        self.min_edge = 10.0  # Edge minimum 10%
        self.min_score = 65   # Score minimum pour être value bet
    
    def detect_value_bets(self, race: Race) -> Race:
        """
        Analyse tous les chevaux et marque les value bets.
        
        Args:
            race: Course avec scores calculés
        
        Returns:
            Race avec value_bets détectés
        """
        logger.info("Détection Value Bets...")
        
        for horse in race.horses:
            self._analyze_horse_value(horse)
        
        value_bets = race.get_value_bets()
        logger.info(f"✓ {len(value_bets)} Value Bet(s) détecté(s)")
        
        for vb in value_bets:
            logger.info(f"  #{vb.numero} {vb.nom}: edge {vb.edge_percent}% (cote {vb.cote})")
        
        return race
    
    def _analyze_horse_value(self, horse: Horse):
        """Analyse si un cheval est un value bet."""
        
        # Critères d'exclusion rapide
        if horse.score_total < self.min_score:
            return
        
        if horse.cote < 5.0:
            # Favoris rarement value
            return
        
        # Calcul probabilité implicite de la cote
        prob_cote = 1 / horse.cote * 100  # En %
        
        # Estimation probabilité basée sur score (approximation)
        prob_score = self._estimate_probability_from_score(horse.score_total)
        
        # Calcul edge
        edge = prob_score - prob_cote
        
        # Est-ce un value bet ?
        if edge >= self.min_edge:
            horse.is_value_bet = True
            horse.edge_percent = round(edge, 1)
            
            # Confidence du value bet
            if edge >= 20:
                horse.vb_confidence = "FORTE"
            elif edge >= 15:
                horse.vb_confidence = "MODEREE"
            else:
                horse.vb_confidence = "FAIBLE"
            
            # Analyse causes sous-cotation
            self._analyze_undercote_reasons(horse)
    
    def _estimate_probability_from_score(self, score: int) -> float:
        """
        Estime la probabilité de placement basée sur le score.
        
        Mapping approximatif:
        - 90+ pts → 30% chance placement top 3
        - 80-89 pts → 25%
        - 70-79 pts → 20%
        - 65-69 pts → 15%
        """
        if score >= 90:
            return 30.0
        elif score >= 85:
            return 27.0
        elif score >= 80:
            return 25.0
        elif score >= 75:
            return 22.0
        elif score >= 70:
            return 20.0
        elif score >= 65:
            return 15.0
        else:
            return 10.0
    
    def _analyze_undercote_reasons(self, horse: Horse):
        """Identifie pourquoi un cheval est sous-coté."""
        reasons = []
        
        # Ferrure récente
        if 'deferre' in horse.bonuses:
            reasons.append("déferré récemment")
        
        # Driver élite
        if 'driver_elite' in horse.bonuses:
            reasons.append("driver élite")
        
        # Chrono excellent
        if 'chrono_excellent' in horse.bonuses:
            reasons.append("chrono excellent")
        
        # Forme récente
        if horse.musique and horse.musique[:3].count('1') >= 2:
            reasons.append("en série (2+ victoires récentes)")
        
        # Avis positif
        if 'avis_positif' in horse.bonuses:
            reasons.append("avis entraîneur positif")
        
        # Spécialité inversée (retour à spécialité favorite)
        if horse.specialite_inversee and horse.specialite == horse.specialite_actuelle:
            reasons.append("retour à spécialité favorite")
        
        # Stock dans métadonnées
        if reasons:
            horse.bonuses['value_reasons'] = ", ".join(reasons)


# ============================================================================
# VALIDATION MODULE
# ============================================================================

if __name__ == "__main__":
    from core.scraper import PMUScraper
    from core.scoring_engine import ScoringEngine
    
    print("=" * 70)
    print("TROT SYSTEM v8.0 - TEST VALUE BET DETECTOR")
    print("=" * 70)
    
    # Récupération + scoring
    scraper = PMUScraper()
    race = scraper.get_race_data("15122025", 1, 4)
    
    if race:
        engine = ScoringEngine()
        race = engine.score_race(race)
        
        # Détection value bets
        detector = ValueBetDetector()
        race = detector.detect_value_bets(race)
        
        print(f"\n✓ Analyse terminée")
        
        value_bets = race.get_value_bets()
        if value_bets:
            print(f"\n  {len(value_bets)} Value Bet(s) détecté(s):")
            for vb in value_bets:
                print(f"\n    #{vb.numero} {vb.nom}")
                print(f"    Score: {vb.score_total}/100 | Cote: {vb.cote}")
                print(f"    Edge: {vb.edge_percent}% ({vb.vb_confidence})")
                if 'value_reasons' in vb.bonuses:
                    print(f"    Raisons: {vb.bonuses['value_reasons']}")
        else:
            print("\n  Aucun Value Bet détecté")
    
    print("\n" + "=" * 70)
