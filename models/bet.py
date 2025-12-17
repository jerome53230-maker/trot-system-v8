# ============================================================================
# TROT SYSTEM v8.0 - MODÈLES DE PARIS
# ============================================================================

from dataclasses import dataclass
from typing import List, Dict

@dataclass
class BetRecommendation:
    """Représente une recommandation de pari."""
    
    type: str  # "SIMPLE_GAGNANT" | "SIMPLE_PLACE" | "COUPLE_GAGNANT" etc.
    chevaux: List[int]
    chevaux_noms: List[str]
    mise: float
    roi_attendu: float
    justification: str
    
    def validate(self) -> tuple[bool, str]:
        """
        Valide la cohérence du pari.
        
        Returns:
            (is_valid, error_message)
        """
        # Validation longueur chevaux
        expected_lengths = {
            "SIMPLE_GAGNANT": 1,
            "SIMPLE_PLACE": 1,
            "COUPLE_GAGNANT": 2,
            "COUPLE_PLACE": 2,
            "TRIO": 3,
            "MULTI_EN_4": 4,
            "MULTI_EN_5": 5,
            "DEUX_SUR_QUATRE": 4,
        }
        
        expected = expected_lengths.get(self.type)
        if expected is None:
            return False, f"Type pari invalide: {self.type}"
        
        if len(self.chevaux) != expected:
            return False, f"{self.type} nécessite {expected} chevaux, reçu {len(self.chevaux)}"
        
        # Validation mise minimale
        min_mises = {
            "SIMPLE_GAGNANT": 1.50,
            "SIMPLE_PLACE": 1.50,
            "COUPLE_GAGNANT": 1.50,
            "COUPLE_PLACE": 1.50,
            "TRIO": 2.00,
            "MULTI_EN_4": 3.00,
            "MULTI_EN_5": 3.00,
            "DEUX_SUR_QUATRE": 3.00,
        }
        
        min_mise = min_mises.get(self.type, 0)
        if self.mise < min_mise:
            return False, f"{self.type} mise min {min_mise}€, reçu {self.mise}€"
        
        return True, ""


@dataclass
class RaceAnalysis:
    """Résultat complet d'analyse d'une course."""
    
    # Scénario détecté
    scenario_course: str  # "CADENAS" | "BATAILLE" | "SURPRISE" | "PIEGE" | "NON_JOUABLE"
    analyse_tactique: str
    
    # Top chevaux
    top_5_chevaux: List[Dict]
    
    # Value Bets
    value_bets_detectes: List[Dict]
    
    # Paris
    paris_recommandes: List[BetRecommendation]
    
    # Budget
    budget_total: float
    budget_utilise: float
    roi_moyen_attendu: float
    
    # Conseil
    conseil_final: str
    confiance_globale: int
    
    def to_dict(self) -> dict:
        """Convertit en dictionnaire pour JSON."""
        return {
            "scenario_course": self.scenario_course,
            "analyse_tactique": self.analyse_tactique,
            "top_5_chevaux": self.top_5_chevaux,
            "value_bets_detectes": self.value_bets_detectes,
            "paris_recommandes": [
                {
                    "type": bet.type,
                    "chevaux": bet.chevaux,
                    "chevaux_noms": bet.chevaux_noms,
                    "mise": bet.mise,
                    "roi_attendu": bet.roi_attendu,
                    "justification": bet.justification
                }
                for bet in self.paris_recommandes
            ],
            "budget_total": self.budget_total,
            "budget_utilise": self.budget_utilise,
            "roi_moyen_attendu": self.roi_moyen_attendu,
            "conseil_final": self.conseil_final,
            "confiance_globale": self.confiance_globale
        }
    
    def validate_budget(self, tolerance: float = 0.50) -> tuple[bool, str]:
        """
        Valide le respect du budget.
        
        Args:
            tolerance: Tolérance en euros
        
        Returns:
            (is_valid, message)
        """
        if self.budget_utilise > self.budget_total + tolerance:
            return False, f"Budget dépassé: {self.budget_utilise}€ > {self.budget_total + tolerance}€"
        
        if not self.paris_recommandes and self.scenario_course != "NON_JOUABLE":
            return False, "Aucun pari recommandé pour course jouable"
        
        return True, "Budget OK"


@dataclass
class Debrief:
    """Débriefing post-course avec résultats réels."""
    
    # Identité course
    date: str
    reunion: int
    course: int
    hippodrome: str
    
    # Résultats réels
    arrivee: List[int]  # Numéros dans l'ordre
    non_partants: List[int]
    
    # Performance paris
    paris_joues: List[BetRecommendation]
    paris_gagnants: List[str]  # Types gagnants
    gains_total: float
    mise_totale: float
    roi_reel: float
    
    # Analyse
    top_5_predit: List[int]
    top_5_reel: List[int]
    precision_top_3: float  # % chevaux top 3 prédits dans top 3 réel
    
    commentaire: str
    
    def to_dict(self) -> dict:
        """Convertit en dictionnaire."""
        return {
            "date": self.date,
            "reunion": self.reunion,
            "course": self.course,
            "hippodrome": self.hippodrome,
            "arrivee": self.arrivee,
            "non_partants": self.non_partants,
            "paris_gagnants": self.paris_gagnants,
            "gains_total": self.gains_total,
            "mise_totale": self.mise_totale,
            "roi_reel": self.roi_reel,
            "precision_top_3": self.precision_top_3,
            "commentaire": self.commentaire
        }
