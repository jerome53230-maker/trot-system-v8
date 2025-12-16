# ============================================================================
# TROT SYSTEM v8.0 - MOTEUR DE SCORING
# ============================================================================

from models.race import Race, Horse
from core.track_coefficients import normalize_chrono, get_track_info
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class ScoringEngine:
    """Moteur de calcul des scores pour chaque cheval."""
    
    def __init__(self):
        self.weights = {
            'performance': 30,
            'chrono': 25,
            'entourage': 20,
            'physique': 15,
            'contexte': 10
        }
    
    def score_race(self, race: Race) -> Race:
        """
        Calcule les scores de tous les chevaux d'une course.
        
        Args:
            race: Objet Race avec données brutes
        
        Returns:
            Race avec scores calculés
        """
        logger.info(f"Scoring {race.nb_partants} chevaux pour {race.hippodrome}...")
        
        # 1. Normalisation chronos
        self._normalize_all_chronos(race)
        
        # 2. Calcul scores individuels
        for horse in race.horses:
            self._score_horse(horse, race)
        
        # 3. Calcul indicateurs globaux
        self._calculate_global_indicators(race)
        
        # 4. Détection favoris
        self._detect_favoris(race)
        
        logger.info(f"✓ Scoring terminé. Top 3:")
        top_3 = race.get_top_horses(3)
        for i, h in enumerate(top_3, 1):
            logger.info(f"  {i}. #{h.numero} {h.nom}: {h.score_total}/100 ({h.risk_profile})")
        
        return race
    
    def _normalize_all_chronos(self, race: Race):
        """Normalise les chronos de tous les chevaux relativement à l'hippodrome."""
        track_info = get_track_info(race.hippodrome)
        logger.info(f"Normalisation chronos pour {race.hippodrome} (coef: {track_info['coefficient']}s)")
        
        for horse in race.horses:
            if horse.dernier_chrono:
                horse.chrono_normalise = normalize_chrono(
                    horse.dernier_chrono, 
                    race.hippodrome, 
                    race.distance
                )
                
                # Calcul écart vs référence Vincennes (1'12" = 72s pour 2700m)
                reference_time = self._get_reference_time(race.distance)
                horse.ecart_vs_reference = horse.chrono_normalise - reference_time
    
    def _get_reference_time(self, distance: int) -> float:
        """Retourne le temps de référence pour une distance donnée."""
        # Temps références Vincennes (élite)
        references = {
            2100: 66.0,   # 1'06"
            2700: 72.0,   # 1'12"
            2850: 75.0,   # 1'15"
            4150: 105.0,  # 1'45"
        }
        
        # Interpolation linéaire si distance exacte absente
        closest = min(references.keys(), key=lambda x: abs(x - distance))
        return references.get(closest, 72.0)
    
    def _score_horse(self, horse: Horse, race: Race):
        """Calcule le score total d'un cheval."""
        
        # 1. Performance (30 pts)
        horse.score_performance = self._score_performance(horse)
        
        # 2. Chrono (25 pts)
        horse.score_chrono = self._score_chrono(horse, race)
        
        # 3. Entourage (20 pts)
        horse.score_entourage = self._score_entourage(horse)
        
        # 4. Physique (15 pts)
        horse.score_physique = self._score_physique(horse)
        
        # 5. Contexte (10 pts)
        horse.score_contexte = self._score_contexte(horse, race)
        
        # Score total
        horse.score_total = (
            horse.score_performance +
            horse.score_chrono +
            horse.score_entourage +
            horse.score_physique +
            horse.score_contexte
        )
        
        # Métadonnées
        self._calculate_metadata(horse)
    
    def _score_performance(self, horse: Horse) -> int:
        """Score performance (30 pts) basé sur musique et ratio victoires."""
        score = 0
        missing_data = []
        
        # Ratio victoires/courses (15 pts)
        if horse.nb_courses > 0:
            ratio_victoires = horse.nb_victoires / horse.nb_courses
            score += min(15, int(ratio_victoires * 100))
            
            # Bonus régularité (places)
            if horse.nb_courses >= 5:
                ratio_places = (horse.nb_victoires + horse.nb_places) / horse.nb_courses
                if ratio_places >= 0.6:
                    score += 5
                    horse.bonuses['regularite'] = 5
        else:
            missing_data.append('nb_courses')
        
        # Musique récente (15 pts)
        if horse.musique:
            # Analyse 5 dernières courses
            recent = horse.musique[:5]
            victoires_recentes = recent.count('1')
            places_recentes = recent.count('2') + recent.count('3')
            
            score += victoires_recentes * 5
            score += places_recentes * 2
        else:
            missing_data.append('musique')
        
        horse.missing_data.extend(missing_data)
        return min(30, score)
    
    def _score_chrono(self, horse: Horse, race: Race) -> int:
        """Score chrono (25 pts) basé sur chronos normalisés."""
        score = 0
        
        if not horse.chrono_normalise:
            horse.missing_data.append('chrono')
            return 0
        
        # Écart vs référence
        if horse.ecart_vs_reference is not None:
            if horse.ecart_vs_reference <= -1.5:
                # Excellent (-1.5s ou mieux)
                score = 25
                horse.bonuses['chrono_excellent'] = 5
            elif horse.ecart_vs_reference <= -0.5:
                # Très bon
                score = 20
            elif horse.ecart_vs_reference <= 0.5:
                # Bon
                score = 15
            elif horse.ecart_vs_reference <= 1.5:
                # Moyen
                score = 10
            else:
                # Faible
                score = 5
                horse.penalties['chrono_faible'] = -5
        
        return score
    
    def _score_entourage(self, horse: Horse) -> int:
        """Score entourage (20 pts) driver + entraîneur + avis."""
        score = 10  # Base
        
        # Driver élite (liste non exhaustive, à compléter)
        elite_drivers = [
            'NIVARD', 'ABRIVARD', 'MOTTIER', 'LEBELLER', 'VERVA',
            'LECANU', 'RAFFIN', 'BRIAND', 'BARRIER', 'LOCQUENEUX'
        ]
        
        if any(d in horse.driver.upper() for d in elite_drivers):
            score += 5
            horse.bonuses['driver_elite'] = 5
        
        # Avis entraîneur
        if horse.avis_entraineur == 'POSITIF':
            score += 5
            horse.bonuses['avis_positif'] = 5
        elif horse.avis_entraineur == 'NEGATIF':
            score -= 3
            horse.penalties['avis_negatif'] = -3
        
        return min(20, max(0, score))
    
    def _score_physique(self, horse: Horse) -> int:
        """Score physique (15 pts) ferrure + âge."""
        score = 10  # Base
        
        # Déferré (signal fort)
        if horse.deferre in ['4', 'D4', 'DP']:
            score += 5
            horse.bonuses['deferre'] = 5
        elif horse.deferre in ['2AP', '2A']:
            score += 3
            horse.bonuses['deferre_partiel'] = 3
        
        # Âge optimal (4-8 ans)
        if 4 <= horse.age <= 8:
            score += 2
        elif horse.age > 10:
            score -= 2
            horse.penalties['age_eleve'] = -2
        
        return min(15, max(0, score))
    
    def _score_contexte(self, horse: Horse, race: Race) -> int:
        """Score contexte (10 pts) affinité hippodrome + spécialité."""
        score = 5  # Base
        
        # Affinité hippodrome
        if race.hippodrome in horse.hippodrome_affinite:
            score += 3
            horse.bonuses['affinite_hippodrome'] = 3
        
        # Spécialité inversée (ATTELE → MONTE ou inverse)
        if horse.specialite_inversee:
            score -= 2
            horse.penalties['specialite_inversee'] = -2
        
        return min(10, max(0, score))
    
    def _calculate_metadata(self, horse: Horse):
        """Calcule confidence et risk_profile."""
        
        # Confidence basée sur données manquantes
        missing_count = len(horse.missing_data)
        if missing_count == 0:
            horse.confidence = "HIGH"
        elif missing_count <= 2:
            horse.confidence = "MEDIUM"
        else:
            horse.confidence = "LOW"
        
        # Risk profile basé sur score + cote
        if horse.score_total >= 80:
            horse.risk_profile = "SECURITE"
        elif horse.score_total >= 70:
            horse.risk_profile = "REGULIER"
        elif horse.score_total >= 60:
            horse.risk_profile = "RISQUE"
        else:
            horse.risk_profile = "OUTSIDER"
        
        # Ajustement par cote
        if horse.cote < 4 and horse.score_total >= 75:
            horse.risk_profile = "SECURITE"
        elif horse.cote > 15 and horse.score_total < 70:
            horse.risk_profile = "OUTSIDER"
    
    def _calculate_global_indicators(self, race: Race):
        """Calcule les indicateurs globaux de la course."""
        
        # Qualité données (% chevaux avec données complètes)
        complete_horses = sum(1 for h in race.horses if len(h.missing_data) <= 1)
        race.qualite_donnees = int((complete_horses / race.nb_partants) * 100)
        
        # Données manquantes (%)
        total_missing = sum(len(h.missing_data) for h in race.horses)
        max_possible = race.nb_partants * 5  # 5 critères max
        race.donnees_manquantes_pct = round((total_missing / max_possible) * 100, 1)
        
        # Confiance globale (1-10)
        if race.qualite_donnees >= 90:
            race.confiance_globale = 9
        elif race.qualite_donnees >= 80:
            race.confiance_globale = 8
        elif race.qualite_donnees >= 70:
            race.confiance_globale = 7
        elif race.qualite_donnees >= 60:
            race.confiance_globale = 6
        else:
            race.confiance_globale = 5
    
    def _detect_favoris(self, race: Race):
        """Marque les favoris (cote < 5)."""
        for horse in race.horses:
            if horse.cote < 5.0:
                horse.is_favoris = True


# ============================================================================
# VALIDATION MODULE
# ============================================================================

if __name__ == "__main__":
    from core.scraper import PMUScraper
    
    print("=" * 70)
    print("TROT SYSTEM v8.0 - TEST SCORING ENGINE")
    print("=" * 70)
    
    # Récupération course
    scraper = PMUScraper()
    race = scraper.get_race_data("15122025", 1, 4)
    
    if race:
        # Scoring
        engine = ScoringEngine()
        race = engine.score_race(race)
        
        print(f"\n✓ Scoring terminé pour {race.hippodrome}")
        print(f"  Qualité données: {race.qualite_donnees}/100")
        print(f"  Confiance globale: {race.confiance_globale}/10")
        
        print(f"\n  Top 5 chevaux:")
        for i, h in enumerate(race.get_top_horses(5), 1):
            print(f"    {i}. #{h.numero} {h.nom}")
            print(f"       Score: {h.score_total}/100 ({h.risk_profile})")
            print(f"       Cote: {h.cote} | Confidence: {h.confidence}")
    
    print("\n" + "=" * 70)
