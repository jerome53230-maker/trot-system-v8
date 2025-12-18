# ============================================================================
# TROT SYSTEM v8.0 - SCRAPER PMU (VERSION FINALE - POST DIAGNOSTIC)
# ============================================================================

import requests
from typing import Optional, Dict, List
from datetime import datetime, date, timedelta
from models.race import Race, Horse
import logging
import time
import random

logger = logging.getLogger(__name__)

class PMUScraper:
    """Scraper pour récupérer les données de courses PMU."""
    
    BASE_URL = "https://online.turfinfo.api.pmu.fr/rest/client/1"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        print("🎯 NOUVEAU SCRAPER V2 CHARGÉ !")
        logger.info("🎯 PMUScraper V2 initialisé (endpoint /participants validé)")
        logger.info("✓ Scraper PMU initialisé")
    
    def get_race_data(self, date_str: str, reunion: int, course: int) -> Optional[Race]:
        """
        Récupère les données complètes d'une course.
        
        Basé sur diagnostic: utilise l'endpoint /participants qui fonctionne.
        
        Args:
            date_str: Date format "DDMMYYYY" (ex: "15122025")
            reunion: Numéro réunion (1-9)
            course: Numéro course (1-16)
        
        Returns:
            Objet Race complet ou None si erreur
        """
        print(f"🎯 SCRAPER V2 DÉMARRAGE: {date_str} R{reunion}C{course}")
        logger.info(f"🎯 SCRAPER V2 DÉMARRAGE: {date_str} R{reunion}C{course}")
        logger.info(f"📊 Scraping: {date_str} R{reunion}C{course}")
        
        try:
            # Format date
            race_date = datetime.strptime(date_str, "%d%m%Y").date()
            
            # URL de base
            course_url = f"{self.BASE_URL}/programme/{date_str}/R{reunion}/C{course}"
            
            # === ÉTAPE 1: Infos course (sans participants) ===
            logger.info(f"📥 Étape 1: Infos course: {course_url}")
            course_data = self._fetch_json(course_url)
            
            if not course_data:
                logger.error(f"❌ Course R{reunion}C{course} introuvable")
                return None
            
            logger.info(f"✓ Étape 1 OK: Course data récupérée")
            
            # === ÉTAPE 2: Participants (endpoint séparé - VALIDÉ PAR DIAGNOSTIC) ===
            participants_url = f"{course_url}/participants"
            logger.info(f"📥 Étape 2: Participants: {participants_url}")
            
            part_response = self._fetch_json(participants_url)
            
            if not part_response:
                logger.error(f"❌ Participants introuvables")
                return None
            
            logger.info(f"✓ Étape 2 OK: Participants response récupérée")
            
            # Extraire participants (format validé par diagnostic)
            if isinstance(part_response, dict) and 'participants' in part_response:
                participants = part_response['participants']
                logger.info(f"✓ Format: Dict avec 'participants' - {len(participants)} éléments")
            elif isinstance(part_response, list):
                participants = part_response
                logger.info(f"✓ Format: Liste directe - {len(participants)} éléments")
            else:
                logger.error(f"❌ Format participants inconnu: {type(part_response)}")
                return None
            
            # Validation format
            if not participants or len(participants) == 0:
                logger.warning("⚠️ Aucun participant")
                return None
            
            first_participant = participants[0]
            if not isinstance(first_participant, dict):
                logger.error(f"❌ Participant invalide: {type(first_participant)}")
                return None
            
            logger.info(f"✓ {len(participants)} participants valides (dicts)")
            
            # Ajouter participants aux données
            course_data['participants'] = participants
            
            logger.info(f"📥 Étape 3: Construction Race...")
            
            # === ÉTAPE 3: Construction Race ===
            race = self._build_race_object(course_data, race_date, reunion, course)
            
            logger.info(f"✅ {race.hippodrome}: {race.nb_partants} chevaux")
            return race
            
        except Exception as e:
            logger.error(f"❌ Erreur scraping: {e}", exc_info=True)
            return None
    
    def _fetch_json(self, url: str, retry_count: int = 2) -> Optional[Dict]:
        """
        Récupère et parse JSON avec retry et exponential backoff.
        
        Intègre corrections ChatGPT:
        - Exponential backoff avec jitter
        - Gestion 429 Too Many Requests
        - Logs structurés
        """
        for attempt in range(retry_count + 1):
            try:
                response = self.session.get(url, timeout=15)
                
                # Gestion codes erreur
                if response.status_code == 200:
                    return response.json()
                    
                elif response.status_code == 404:
                    logger.warning(f"404 Not Found: {url}")
                    return None
                    
                elif response.status_code == 429:
                    # Too Many Requests - attendre plus longtemps
                    if attempt < retry_count:
                        wait_time = 2 ** (attempt + 2)  # 4s, 8s, etc.
                        jitter = random.uniform(0, 0.5)
                        logger.warning(f"429 Too Many Requests, attente {wait_time+jitter:.1f}s")
                        time.sleep(wait_time + jitter)
                        continue
                    return None
                    
                elif response.status_code == 503:
                    # Service Unavailable - retry avec backoff
                    if attempt < retry_count:
                        wait_time = 2 ** attempt
                        jitter = random.uniform(0, 0.5)
                        logger.warning(f"503 Service Unavailable, retry dans {wait_time+jitter:.1f}s")
                        time.sleep(wait_time + jitter)
                        continue
                    return None
                    
                else:
                    logger.error(f"HTTP {response.status_code}: {url}")
                    return None
                    
            except requests.Timeout:
                if attempt < retry_count:
                    logger.warning(f"Timeout {url}, retry {attempt+1}/{retry_count}")
                    time.sleep(1 + random.uniform(0, 0.5))
                    continue
                logger.error(f"Timeout final: {url}")
                return None
                
            except requests.ConnectionError as e:
                if attempt < retry_count:
                    logger.warning(f"Erreur connexion, retry")
                    time.sleep(2 + random.uniform(0, 0.5))
                    continue
                logger.error(f"Erreur connexion finale: {e}")
                return None
                
            except requests.exceptions.JSONDecodeError:
                logger.error(f"Réponse non-JSON: {url}")
                return None
                
            except Exception as e:
                logger.error(f"Erreur inattendue: {e}")
                return None
        
        return None
    
    def _build_race_object(self, course_data: Dict, race_date: date, 
                          reunion: int, course: int) -> Race:
        """Construit un objet Race à partir des données PMU."""
        
        # Infos course
        hippodrome_data = course_data.get('hippodrome', {})
        if isinstance(hippodrome_data, dict):
            hippodrome = hippodrome_data.get('libelleCourt', 'INCONNU')
        else:
            hippodrome = 'INCONNU'
            
        distance = course_data.get('distance', 0)
        discipline = course_data.get('discipline', 'ATTELE')  # Directement dans course_data
        type_depart = course_data.get('libelleDepartFr', 'INCONNU')
        montant = course_data.get('montantPrix', 0)
        etat_piste = 'BON'  # Pas dans API
        
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
        if 'attele' in discipline_code.lower() or 'attelé' in discipline_code.lower():
            return 'ATTELE'
        elif 'monte' in discipline_code.lower() or 'monté' in discipline_code.lower():
            return 'MONTE'
        return 'ATTELE'  # Par défaut
    
    def _extract_horses(self, course_data: Dict, discipline: str, hippodrome: str) -> List[Horse]:
        """Extrait la liste des chevaux participants."""
        print(f"🔨 _extract_horses APPELÉ")
        logger.info(f"🔨 _extract_horses: Début extraction")
        
        horses = []
        participants = course_data.get('participants', [])
        
        logger.info(f"📋 {len(participants)} participants à traiter")
        
        for i, p in enumerate(participants):
            try:
                # Vérification type CRITIQUE
                if not isinstance(p, dict):
                    logger.error(f"❌ Participant #{i+1} n'est pas un dict: {type(p)}")
                    continue
                
                horse = self._build_horse(p, discipline, hippodrome)
                horses.append(horse)
                
            except ValueError as e:
                logger.warning(f"⚠️ Cheval #{i+1} ignoré: {e}")
                continue
            except Exception as e:
                logger.error(f"❌ Erreur cheval #{i+1}: {e}")
                continue
        
        logger.info(f"✓ {len(horses)}/{len(participants)} chevaux extraits")
        return horses
    
    def _build_horse(self, participant: Dict, discipline: str, hippodrome: str) -> Horse:
        """Construit un objet Horse avec validation."""
        
        # Numéro (obligatoire)
        numero = participant.get('numPmu', 0)
        if numero <= 0:
            raise ValueError(f"Numéro invalide: {numero}")
        
        # Nom (obligatoire)
        nom = participant.get('nom', '').strip()
        if not nom:
            raise ValueError(f"Nom manquant pour #{numero}")
        
        # Entourage
        driver = participant.get('driver', '') if participant.get('driver') else ''
        entraineur = participant.get('entraineur', '') if participant.get('entraineur') else ''
        proprietaire = participant.get('proprietaire', '') if participant.get('proprietaire') else ''
        
        # Performances
        musique = participant.get('musique', '')
        nb_courses = max(0, participant.get('nombreCourses', 0))
        nb_victoires = max(0, participant.get('nombreVictoires', 0))
        nb_places = max(0, participant.get('nombrePlaces', 0))
        
        # Gains (structure nested)
        gains_data = participant.get('gainsParticipant', {})
        gains = max(0, gains_data.get('gainsCarriere', 0)) if isinstance(gains_data, dict) else 0
        
        # Validation cohérence
        if nb_victoires > nb_places:
            nb_places = nb_victoires
        if nb_places > nb_courses:
            nb_courses = nb_places
        
        # Chronos - Pas dans API participants
        dernier_chrono = None
        meilleur_chrono = None
        
        # Cote probable (dernierRapportDirect ou dernierRapportReference)
        cote_probable = None
        rapport_direct = participant.get('dernierRapportDirect', {})
        if isinstance(rapport_direct, dict) and 'rapport' in rapport_direct:
            cote_probable = rapport_direct.get('rapport')
        else:
            rapport_ref = participant.get('dernierRapportReference', {})
            if isinstance(rapport_ref, dict) and 'rapport' in rapport_ref:
                cote_probable = rapport_ref.get('rapport')
        
        # Autres infos
        deferre = '0'  # Pas dans API
        avis = participant.get('avisEntraineur', 'NEUTRE')
        age = participant.get('age', 0)
        sexe = participant.get('sexe', '')
        
        return Horse(
            numero=numero,
            nom=nom,
            driver=driver,
            entraineur=entraineur,
            proprietaire=proprietaire,
            musique=musique,
            nb_courses=nb_courses,  # ✅ CORRIGÉ !
            nb_victoires=nb_victoires,  # ✅ CORRIGÉ !
            nb_places=nb_places,  # ✅ CORRIGÉ !
            gains_carriere=gains,
            dernier_chrono=dernier_chrono,
            meilleur_chrono=meilleur_chrono,
            cote=cote_probable if cote_probable else 0.0,  # ✅ CORRIGÉ !
            deferre=deferre,
            specialite=discipline,
            avis_entraineur=avis,
            age=age,
            sexe=sexe
        )
    
    def _parse_chrono(self, chrono_str) -> Optional[float]:
        """Parse un chrono au format "1'23''4" vers secondes."""
        if not chrono_str or chrono_str == '':
            return None
        
        try:
            chrono_str = str(chrono_str).strip()
            
            # Format: 1'23''4 ou 1'23"4
            if "'" in chrono_str:
                parts = chrono_str.replace("''", ".").replace('"', '.').split("'")
                minutes = int(parts[0])
                secondes_str = parts[1].replace("'", "")
                secondes = float(secondes_str)
                return minutes * 60 + secondes
            
            # Format déjà en secondes
            return float(chrono_str)
            
        except Exception:
            return None
    
    def _parse_cote(self, cote_raw) -> Optional[float]:
        """Parse une cote."""
        if not cote_raw:
            return None
        
        try:
            if isinstance(cote_raw, (int, float)):
                return float(cote_raw)
            
            cote_str = str(cote_raw).strip()
            if '/' in cote_str:
                num, den = cote_str.split('/')
                return float(num) / float(den)
            
            return float(cote_str)
            
        except Exception:
            return None
    
    def get_race_results(self, date_str: str, reunion: int, course: int) -> Optional[Dict]:
        """Récupère les résultats d'une course terminée."""
        try:
            url = f"{self.BASE_URL}/programme/{date_str}/R{reunion}/C{course}/rapports-definitifs"
            logger.info(f"📥 Résultats: {url}")
            
            data = self._fetch_json(url)
            if not data:
                return None
            
            # Extraire arrivée
            arrivee_raw = data.get('ordreArrivee', '')
            arrivee = [int(x) for x in arrivee_raw.split('-') if x.isdigit()]
            
            # Extraire rapports
            rapports = {}
            for rapport in data.get('rapports', []):
                type_pari = rapport.get('typePari', '')
                montant = rapport.get('montant', 0)
                rapports[type_pari] = montant
            
            return {
                'arrivee': arrivee,
                'rapports': rapports
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur résultats: {e}")
            return None
