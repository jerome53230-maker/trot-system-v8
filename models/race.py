# ============================================================================
# TROT SYSTEM v8.0 - MODÈLES DE DONNÉES COURSES
# ============================================================================

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import date

@dataclass
class Horse:
    """Représente un cheval dans une course."""
    
    # Identité
    numero: int
    nom: str
    sexe: str = ""
    age: int = 0
    
    # Entourage
    driver: str = ""
    driver_form: str = ""  # "EN_SERIE" | "NORMAL" | "DIFFICILE"
    entraineur: str = ""
    proprietaire: str = ""
    
    # Performance
    musique: str = ""
    nb_courses: int = 0
    nb_victoires: int = 0
    nb_places: int = 0
    gains_carriere: int = 0
    
    # Chronos
    dernier_chrono: Optional[float] = None
    meilleur_chrono: Optional[float] = None
    chrono_normalise: Optional[float] = None
    ecart_vs_reference: Optional[float] = None
    
    # Tactique
    specialite: str = ""  # "ATTELE" | "MONTE"
    specialite_actuelle: str = ""
    specialite_inversee: bool = False
    deferre: str = "0"  # "0" | "2AP" | "4" | "D4" etc.
    distance_optimale: Optional[int] = None
    hippodrome_affinite: List[str] = field(default_factory=list)
    
    # Avis
    avis_entraineur: str = ""  # "POSITIF" | "NÉGATIF" | "NEUTRE"
    avis_presse: str = ""
    
    # Cotation
    cote: float = 0.0
    is_favoris: bool = False
    
    # Scores (pré-calculés par Python)
    score_total: int = 0
    score_performance: int = 0
    score_chrono: int = 0
    score_entourage: int = 0
    score_physique: int = 0
    score_contexte: int = 0
    
    # Métadonnées scoring
    confidence: str = ""  # "HIGH" | "MEDIUM" | "LOW"
    risk_profile: str = ""  # "SECURITE" | "REGULIER" | "RISQUE" | "OUTSIDER"
    missing_data: List[str] = field(default_factory=list)
    bonuses: Dict[str, int] = field(default_factory=dict)
    penalties: Dict[str, int] = field(default_factory=dict)
    
    # Value Bet
    is_value_bet: bool = False
    edge_percent: float = 0.0
    vb_confidence: str = ""
    
    def to_xml(self) -> str:
        """Génère le XML pour le prompt Gemini."""
        return f"""<horse id="{self.numero}" name="{self.nom}">
  <stats>
    <score_total>{self.score_total}/100</score_total>
    <confidence>{self.confidence}</confidence>
    <risk_profile>{self.risk_profile}</risk_profile>
    
    <breakdown>
      <performance>{self.score_performance}/30</performance>
      <chrono>{self.score_chrono}/25</chrono>
      <entourage>{self.score_entourage}/20</entourage>
      <physique>{self.score_physique}/15</physique>
      <contexte>{self.score_contexte}/10</contexte>
    </breakdown>
    
    <metadata>
      <missing_data>{','.join(self.missing_data)}</missing_data>
      <bonuses>{self.bonuses}</bonuses>
      <penalties>{self.penalties}</penalties>
    </metadata>
    
    <odds>
      <cote>{self.cote}</cote>
      <favoris>{self.is_favoris}</favoris>
    </odds>
  </stats>
  
  <value_bet>
    <is_value>{self.is_value_bet}</is_value>
    <edge>{self.edge_percent}%</edge>
    <confidence_vb>{self.vb_confidence}</confidence_vb>
  </value_bet>
  
  <tactical_info>
    <driver>{self.driver}</driver>
    <driver_form>{self.driver_form}</driver_form>
    <entraineur>{self.entraineur}</entraineur>
    <avis_entraineur>{self.avis_entraineur}</avis_entraineur>
    <deferre>{self.deferre}</deferre>
    <specialite_inversee>{self.specialite_inversee}</specialite_inversee>
  </tactical_info>
</horse>"""


@dataclass
class Race:
    """Représente une course hippique complète."""
    
    # Identité
    date: date
    reunion: int
    course: int
    hippodrome: str
    
    # Caractéristiques
    distance: int
    discipline: str  # "ATTELE" | "MONTE"
    type_depart: str  # "AUTOSTART" | "VOLTE"
    montant_prix: int
    nb_partants: int
    
    # Conditions
    etat_piste: str = ""  # "BON" | "SOUPLE" | "LOURD" | "COLLANT"
    impact_piste: str = ""  # Description impact
    
    # Chevaux
    horses: List[Horse] = field(default_factory=list)
    
    # Indicateurs globaux
    confiance_globale: int = 0  # /10
    qualite_donnees: int = 0  # /100
    donnees_manquantes_pct: float = 0.0
    
    def get_top_horses(self, n: int = 5) -> List[Horse]:
        """Retourne les N meilleurs chevaux par score."""
        return sorted(self.horses, key=lambda h: h.score_total, reverse=True)[:n]
    
    def get_value_bets(self) -> List[Horse]:
        """Retourne les chevaux value bet."""
        return [h for h in self.horses if h.is_value_bet]
    
    def to_xml(self) -> str:
        """Génère le XML complet pour le prompt Gemini."""
        horses_xml = '\n'.join([h.to_xml() for h in self.horses])
        
        return f"""<race_context>
<race_info>
  <hippodrome>{self.hippodrome}</hippodrome>
  <reunion>{self.reunion}</reunion>
  <course>{self.course}</course>
  <distance>{self.distance}m</distance>
  <discipline>{self.discipline}</discipline>
  <type_depart>{self.type_depart}</type_depart>
  <dotation>{self.montant_prix}€</dotation>
  <nb_partants>{self.nb_partants}</nb_partants>
  <conditions_piste>
    <etat>{self.etat_piste}</etat>
    <impact>{self.impact_piste}</impact>
  </conditions_piste>
</race_info>

<computed_scores>
{horses_xml}
</computed_scores>

<global_indicators>
  <confiance_globale>{self.confiance_globale}/10</confiance_globale>
  <qualite_donnees>{self.qualite_donnees}/100</qualite_donnees>
  <donnees_manquantes>{self.donnees_manquantes_pct}%</donnees_manquantes>
</global_indicators>
</race_context>"""
