# ============================================================================
# TROT SYSTEM v8.0 - SCRAPER PMU
# ============================================================================

import requests
from typing import Optional, Dict, List
from datetime import datetime, date
from models.race import Race, Horse
import logging

logger = logging.getLogger(__name__)

class PMUScraper:
    """Scraper pour récupérer les données de courses PMU."""
    
    BASE_URL = "https://online.turfinfo.api.pmu.fr/rest/client/1"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_race_data(self, date_str: str, reunion: int, course: int) -> Optional[Race]:
        """
        Récupère les données complètes d'une course.
        
        Args:
            date_str: Date format "DDMMYYYY" (ex: "15122025")
            reunion: Numéro réunion (1-9)
            course: Numéro course (1-16)
        
        Returns:
            Objet Race complet ou None si erreur
        """
        try:
            # Format date - Garder DDMMYYYY tel quel (ex: 16122025)
            race_date = datetime.strptime(date_str, "%d%m%Y").date()
            
            # Récupération données course directe (format API PMU correct)
            course_url = f"{self.BASE_URL}/programme/{date_str}/R{reunion}/C{course}"
            logger.info(f"Récupération course: {course_url}")
            
            course_data = self._fetch_json(course_url)
            if not course_data:
                logger.error(f"Impossible de récupérer la course R{reunion}C{course}")
                return None
            
            # Récupérer les participants (endpoint séparé selon API PMU)
            if 'participants' not in course_data or not course_data.get('participants'):
                participants_url = f"{course_url}/participants"
                logger.info(f"Récupération participants: {participants_url}")
                participants_data = self._fetch_json(participants_url)
                if participants_data and 'participants' in participants_data:
                    course_data['participants'] = participants_data['participants']
                elif participants_data:
                    # Si participants_data est directement la liste
                    course_data['participants'] = participants_data
            
            # Construction objet Race
            race = self._build_race_object(course_data, race_date, reunion, course)
            
            logger.info(f"✓ Course R{reunion}C{course} récupérée: {race.hippodrome}, {race.nb_partants} partants")
            return race
            
        except Exception as e:
            logger.error(f"Erreur scraping: {e}")
            return None
    
    def _fetch_json(self, url: str) -> Optional[Dict]:
        """Récupère et parse JSON d'une URL."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Erreur fetch {url}: {e}")
            return None
    
    def _find_course_in_reunion(self, reunion_data: Dict, course_num: int) -> Optional[Dict]:
        """Trouve une course spécifique dans les données réunion."""
        try:
            courses = reunion_data.get('programme', {}).get('courses', [])
            for course in courses:
                if course.get('numOrdre') == course_num:
                    return course
            return None
        except Exception as e:
            logger.error(f"Erreur recherche course: {e}")
            return None
    
    def _build_race_object(self, course_data: Dict, race_date: date, 
                          reunion: int, course: int) -> Race:
        """Construit un objet Race à partir des données PMU."""
        
        # Infos course
        hippodrome = course_data.get('hippodrome', {}).get('libelleCourt', 'INCONNU')
        distance = course_data.get('distance', 0)
        discipline = self._extract_discipline(course_data)
        type_depart = course_data.get('libelleDepartAbr', 'INCONNU')
        montant = course_data.get('montantPrix', 0)
        
        # Conditions piste
        etat_piste = course_data.get('penetrometre', 'BON')
        
        # Participants
        horses = self._extract_horses(course_data, discipline, hippodrome)
        
        race = Race(
            date=race_date,
            reunion=reunion,
            course=course,
            hippodrome=hippodrome,
            distance=distance,
            discipline=discipline,
            type_depart=type_depart,
            montant_prix=montant,
            nb_partants=len(horses),
            etat_piste=etat_piste,
            horses=horses
        )
        
        return race
    
    def _extract_discipline(self, course_data: Dict) -> str:
        """Extrait la discipline (ATTELE/MONTE)."""
        discipline_code = course_data.get('specialite', '')
        if 'attele' in discipline_code.lower():
            return 'ATTELE'
        elif 'monte' in discipline_code.lower() or 'monté' in discipline_code.lower():
            return 'MONTE'
        return 'ATTELE'  # Par défaut
    
    def _extract_horses(self, course_data: Dict, discipline: str, hippodrome: str) -> List[Horse]:
        """Extrait la liste des chevaux participants."""
        horses = []
        partants = course_data.get('participants', [])
        
        for p in partants:
            try:
                horse = self._build_horse(p, discipline, hippodrome)
                horses.append(horse)
            except Exception as e:
                logger.warning(f"Erreur extraction cheval: {e}")
                continue
        
        return horses
    
    def _build_horse(self, participant: Dict, discipline: str, hippodrome: str) -> Horse:
        """Construit un objet Horse à partir d'un participant."""
        
        # Identité
        numero = participant.get('numPmu', 0)
        nom = participant.get('nom', 'INCONNU')
        
        # Entourage
        driver = participant.get('driver', {}).get('nom', '')
        entraineur = participant.get('entraineur', {}).get('nom', '')
        proprietaire = participant.get('proprietaire', {}).get('nom', '')
        
        # Performance
        musique = participant.get('indicateurInedit', '')
        nb_courses = participant.get('nombreCourses', 0)
        nb_victoires = participant.get('nombreVictoires', 0)
        nb_places = participant.get('nombrePlaces', 0)
        gains = participant.get('gainsCarriere', 0)
        
        # Chronos (à normaliser plus tard)
        dernier_chrono = self._parse_chrono(participant.get('dernierRapportDirect', {}).get('tempsObtenu'))
        meilleur_chrono = self._parse_chrono(participant.get('recordTemps'))
        
        # Tactique
        deferre = participant.get('deferre', '0')
        specialite = discipline
        
        # Avis
        avis = participant.get('avisEntraineur', 'NEUTRE')
        
        # Cote
        cote_data = participant.get('rapportDirect', {})
        cote = cote_data.get('rapportProbable', 0.0)
        if cote == 0:
            cote = 99.0  # Cote inconnue
        
        horse = Horse(
            numero=numero,
            nom=nom,
            driver=driver,
            entraineur=entraineur,
            proprietaire=proprietaire,
            musique=musique,
            nb_courses=nb_courses,
            nb_victoires=nb_victoires,
            nb_places=nb_places,
            gains_carriere=gains,
            dernier_chrono=dernier_chrono,
            meilleur_chrono=meilleur_chrono,
            specialite=specialite,
            specialite_actuelle=discipline,
            deferre=deferre,
            avis_entraineur=avis,
            cote=cote
        )
        
        return horse
    
    def _parse_chrono(self, chrono_str: Optional[str]) -> Optional[float]:
        """
        Parse un chrono format "1'14\"2" en secondes.
        
        Returns:
            Temps en secondes ou None
        """
        if not chrono_str:
            return None
        
        try:
            # Format: 1'14"2 ou 1'14
            chrono_str = str(chrono_str).replace("'", ":").replace('"', '.')
            parts = chrono_str.split(':')
            
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds_str = parts[1].replace(',', '.')
                seconds = float(seconds_str)
                return minutes * 60 + seconds
            
            return None
        except:
            return None
    
    def get_race_results(self, date_str: str, reunion: int, course: int) -> Optional[Dict]:
        """
        Récupère les résultats réels d'une course terminée.
        
        Returns:
            Dict avec arrivée, rapports, etc.
        """
        try:
            # Format date - Garder DDMMYYYY tel quel (ex: 16122025)
            race_date = datetime.strptime(date_str, "%d%m%Y").date()
            
            # Récupération rapports définitifs (format API PMU correct)
            url = f"{self.BASE_URL}/programme/{date_str}/R{reunion}/C{course}/rapports-definitifs"
            logger.info(f"Récupération résultats: {url}")
            
            data = self._fetch_json(url)
            if not data:
                return None
            
            # Extraction arrivée
            arrivee_data = data.get('participants', [])
            arrivee = []
            non_partants = []
            
            for p in arrivee_data:
                numero = p.get('numPmu')
                place = p.get('ordreArrivee')
                
                if p.get('nonPartant'):
                    non_partants.append(numero)
                elif place and numero:
                    arrivee.append((place, numero))
            
            # Tri par ordre d'arrivée
            arrivee.sort()
            arrivee_finale = [num for _, num in arrivee]
            
            # Rapports
            rapports = data.get('rapports', {})
            
            return {
                'arrivee': arrivee_finale,
                'non_partants': non_partants,
                'rapports': rapports
            }
            
        except Exception as e:
            logger.error(f"Erreur récupération résultats: {e}")
            return None


# ============================================================================
# VALIDATION MODULE
# ============================================================================

if __name__ == "__main__":
    # Test scraper
    print("=" * 70)
    print("TROT SYSTEM v8.0 - TEST SCRAPER PMU")
    print("=" * 70)
    
    scraper = PMUScraper()
    
    # Test 1: Récupération course
    print("\n1. Test récupération course")
    race = scraper.get_race_data("15122025", 1, 4)
    
    if race:
        print(f"✓ Course récupérée:")
        print(f"  Hippodrome: {race.hippodrome}")
        print(f"  Distance: {race.distance}m")
        print(f"  Partants: {race.nb_partants}")
        print(f"  Discipline: {race.discipline}")
        
        print(f"\n  Top 3 chevaux:")
        for i, h in enumerate(race.horses[:3], 1):
            print(f"    {i}. #{h.numero} {h.nom} (cote {h.cote})")
    else:
        print("✗ Erreur récupération course")
    
    print("\n" + "=" * 70)
