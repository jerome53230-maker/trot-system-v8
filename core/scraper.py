# ============================================================================
# TROT SYSTEM v8.0 - SCRAPER PMU (OPTIMISÉ)
# ============================================================================

import requests
from typing import Optional, Dict, List
from datetime import datetime, date, timedelta
from models.race import Race, Horse
import logging
import time

logger = logging.getLogger(__name__)

class PMUScraper:
    """Scraper pour récupérer les données de courses PMU (avec cache et retry)."""
    
    BASE_URL = "https://online.turfinfo.api.pmu.fr/rest/client/1"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        # Cache simple avec TTL (Time To Live)
        self._cache = {}
        self._cache_ttl = timedelta(minutes=5)
    
    def get_race_data(self, date_str: str, reunion: int, course: int) -> Optional[Race]:
        """
        Récupère les données complètes d'une course avec cache.
        
        Args:
            date_str: Date format "DDMMYYYY" (ex: "15122025")
            reunion: Numéro réunion (1-9)
            course: Numéro course (1-16)
        
        Returns:
            Objet Race complet ou None si erreur
        """
        # LOG FORCÉ IMMÉDIAT
        print(f"🚨 SCRAPER START: {date_str} R{reunion}C{course}")
        logger.info(f"🚨 SCRAPER get_race_data APPELÉ: {date_str} R{reunion}C{course}")
        
        # CACHE DÉSACTIVÉ TEMPORAIREMENT POUR DEBUG
        # Vérifier cache
        cache_key = f"{date_str}_R{reunion}C{course}"
        logger.info(f"⚠️ CACHE DÉSACTIVÉ POUR DEBUG - Toujours fetch frais")
        # if cache_key in self._cache:
        #     cached_data, cached_time = self._cache[cache_key]
        #     if datetime.now() - cached_time < self._cache_ttl:
        #         logger.info(f"✓ Cache hit: {cache_key}")
        #         return cached_data
        
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
            
            # DEBUG: Log structure course_data
            logger.info(f"🔍 DEBUG: Type course_data = {type(course_data)}")
            logger.info(f"🔍 DEBUG: Clés course_data = {list(course_data.keys()) if isinstance(course_data, dict) else 'N/A'}")
            logger.info(f"🔍 DEBUG: 'participants' présent ? {('participants' in course_data) if isinstance(course_data, dict) else False}")
            
            # === RÉCUPÉRATION PARTICIPANTS (MULTI-ENDPOINTS) ===
            # L'API PMU a plusieurs formats, on teste tous !
            
            participants_found = False
            part_data = None
            
            # Tentative 1 : Déjà dans course_data ?
            if 'participants' in course_data and course_data.get('participants'):
                logger.info("✓ Participants présents dans course_data")
                part_data = course_data['participants']
                participants_found = True
            
            # Tentative 2 : Endpoint /participants séparé
            if not participants_found:
                participants_url = f"{course_url}/participants"
                logger.info(f"📥 Tentative endpoint /participants: {participants_url}")
                part_response = self._fetch_json(participants_url)
                
                if part_response:
                    # Cas A : Liste directe
                    if isinstance(part_response, list):
                        logger.info(f"✓ Format: Liste directe ({len(part_response)} items)")
                        part_data = part_response
                        participants_found = True
                    # Cas B : Dict avec clé 'participants'
                    elif isinstance(part_response, dict) and 'participants' in part_response:
                        logger.info(f"✓ Format: Dict['participants'] ({len(part_response['participants'])} items)")
                        part_data = part_response['participants']
                        participants_found = True
                    # Cas C : Dict avec autre clé
                    elif isinstance(part_response, dict):
                        # Chercher toute clé contenant une liste
                        for key in ['participant', 'partants', 'chevaux', 'runners']:
                            if key in part_response and isinstance(part_response[key], list):
                                logger.info(f"✓ Format: Dict['{key}'] ({len(part_response[key])} items)")
                                part_data = part_response[key]
                                participants_found = True
                                break
            
            # Tentative 3 : Endpoint /performances-detaillees
            if not participants_found:
                perf_url = f"{course_url}/performances-detaillees/pretty"
                logger.info(f"📥 Tentative endpoint /performances-detaillees")
                perf_response = self._fetch_json(perf_url)
                
                if perf_response and isinstance(perf_response, dict):
                    for key in ['participants', 'performances', 'chevaux']:
                        if key in perf_response:
                            part_data = perf_response[key]
                            participants_found = True
                            logger.info(f"✓ Trouvé dans performances-detaillees['{key}']")
                            break
            
            # Vérification finale
            if participants_found and part_data:
                logger.info(f"🎯 Participants trouvés ! Type={type(part_data)}, Len={len(part_data) if isinstance(part_data, (list, dict)) else 'N/A'}")
                
                # Debug: afficher premier élément
                if isinstance(part_data, list) and len(part_data) > 0:
                    first = part_data[0]
                    logger.info(f"🔍 Premier élément: Type={type(first)}, Valeur={str(first)[:100]}")
                
                course_data['participants'] = part_data
            else:
                logger.error("❌ Impossible de trouver les participants dans aucun endpoint !")
                course_data['participants'] = []
            
            
            # DEBUG: Vérifier participants avant construction Race
            logger.info(f"🔍 DEBUG: Avant _build_race_object")
            if isinstance(course_data, dict) and 'participants' in course_data:
                part = course_data['participants']
                logger.info(f"🔍 DEBUG: Type participants final = {type(part)}")
                logger.info(f"🔍 DEBUG: Longueur participants = {len(part) if isinstance(part, (list, dict)) else 'N/A'}")
                if isinstance(part, list) and len(part) > 0:
                    logger.info(f"🔍 DEBUG: Premier participant type = {type(part[0])}")
                    logger.info(f"🔍 DEBUG: Premier participant = {str(part[0])[:150]}")
            
            # Construction objet Race
            race = self._build_race_object(course_data, race_date, reunion, course)
            
            # Mise en cache
            self._cache[cache_key] = (race, datetime.now())
            
            logger.info(f"✓ Course R{reunion}C{course} récupérée: {race.hippodrome}, {race.nb_partants} partants")
            return race
            
        except Exception as e:
            logger.error(f"Erreur scraping: {e}", exc_info=True)
            return None
    
    def _fetch_json(self, url: str, retry_count: int = 2) -> Optional[Dict]:
        """
        Récupère et parse JSON avec retry et meilleure gestion erreurs.
        
        Args:
            url: URL à requêter
            retry_count: Nombre de tentatives en cas d'échec temporaire
        
        Returns:
            Dict JSON ou None
        """
        for attempt in range(retry_count + 1):
            try:
                response = self.session.get(url, timeout=15)
                
                # Gestion codes HTTP explicites
                if response.status_code == 404:
                    logger.warning(f"Ressource introuvable (404): {url}")
                    return None
                elif response.status_code == 503:
                    if attempt < retry_count:
                        wait_time = 2 ** attempt  # Backoff exponentiel
                        logger.warning(f"API temporairement indisponible (503), retry dans {wait_time}s")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"API indisponible après {retry_count} tentatives")
                        return None
                elif response.status_code == 500:
                    logger.error(f"Erreur serveur API (500): {url}")
                    return None
                
                response.raise_for_status()
                return response.json()
                
            except requests.Timeout:
                logger.error(f"Timeout requête {url} (attempt {attempt+1}/{retry_count+1})")
                if attempt < retry_count:
                    time.sleep(1)
                    continue
            except requests.ConnectionError as e:
                logger.error(f"Erreur connexion {url}: {e}")
                if attempt < retry_count:
                    time.sleep(2)
                    continue
            except requests.exceptions.JSONDecodeError as e:
                logger.error(f"Réponse non-JSON de {url}: {e}")
                return None
            except Exception as e:
                logger.error(f"Erreur inattendue {url}: {e}")
                return None
        
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
        
        # Participants avec validation
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
        """Extrait la liste des chevaux participants avec validation."""
        horses = []
        
        # Récupérer participants avec gestion formats multiples
        partants_raw = course_data.get('participants', [])
        
        # DEBUG: Log type et structure
        logger.info(f"🔍 Type participants: {type(partants_raw)}")
        logger.info(f"🔍 Participants échantillon: {str(partants_raw)[:200]}...")
        
        # Gérer différents formats API PMU
        partants = []
        
        if isinstance(partants_raw, list):
            partants = partants_raw
            logger.info(f"✓ Format liste directe: {len(partants)} partants")
        elif isinstance(partants_raw, dict):
            # Si c'est un dict, chercher la liste dedans
            if 'participants' in partants_raw:
                partants = partants_raw['participants']
                logger.info(f"✓ Format dict['participants']: {len(partants)} partants")
            elif 'participant' in partants_raw:
                partants = partants_raw['participant']
                logger.info(f"✓ Format dict['participant']: {len(partants)} partants")
            else:
                # Essayer de trouver une liste dans le dict
                for key, value in partants_raw.items():
                    if isinstance(value, list) and len(value) > 0:
                        partants = value
                        logger.info(f"✓ Participants trouvés sous clé '{key}': {len(partants)}")
                        break
        else:
            logger.error(f"❌ Format participants inconnu: {type(partants_raw)}")
            return horses
        
        logger.info(f"📋 Traitement de {len(partants)} partants...")
        
        for i, p in enumerate(partants):
            try:
                # VÉRIFICATION TYPE CRITIQUE
                if not isinstance(p, dict):
                    logger.error(f"❌ Partant #{i+1} n'est PAS un dict: type={type(p)}, valeur={str(p)[:100]}")
                    continue
                
                horse = self._build_horse(p, discipline, hippodrome)
                horses.append(horse)
                if i < 3:  # Log 3 premiers pour debug
                    logger.info(f"  ✓ Cheval {i+1}: {horse.nom} (#{horse.numero})")
            except ValueError as e:
                logger.warning(f"⚠️ Cheval #{i+1} ignoré (données invalides): {e}")
                continue
            except Exception as e:
                logger.error(f"❌ Erreur extraction cheval #{i+1}: {e}")
                continue
        
        logger.info(f"✅ {len(horses)}/{len(partants)} chevaux extraits avec succès")
        return horses
    
    def _build_horse(self, participant: Dict, discipline: str, hippodrome: str) -> Horse:
        """
        Construit un objet Horse avec validation des données.
        
        Raises:
            ValueError: Si données critiques manquantes ou invalides
        """
        
        # === PROTECTION CRITIQUE: VÉRIFIER TYPE ===
        if not isinstance(participant, dict):
            error_msg = f"Participant n'est PAS un dict ! Type={type(participant)}, Valeur={str(participant)[:200]}"
            logger.error(f"🚨 {error_msg}")
            
            # Si c'est une string, peut-être un nom de cheval ?
            if isinstance(participant, str):
                logger.error(f"🚨 Reçu string au lieu de dict : '{participant}'")
                logger.error(f"🚨 L'API PMU retourne des strings au lieu d'objets !")
                logger.error(f"🚨 Vérifier quel endpoint est utilisé pour récupérer les participants")
            
            raise ValueError(error_msg)
        
        # === VALIDATION DONNÉES CRITIQUES ===
        
        # Numéro (obligatoire)
        numero = participant.get('numPmu', 0)
        if numero <= 0:
            raise ValueError(f"Numéro cheval invalide: {numero}")
        
        # Nom (obligatoire)
        nom = participant.get('nom', '').strip()
        if not nom:
            raise ValueError(f"Nom cheval manquant pour #{numero}")
        
        # === ENTOURAGE ===
        driver = participant.get('driver', {}).get('nom', '') if participant.get('driver') else ''
        entraineur = participant.get('entraineur', {}).get('nom', '') if participant.get('entraineur') else ''
        proprietaire = participant.get('proprietaire', {}).get('nom', '') if participant.get('proprietaire') else ''
        
        # === PERFORMANCE AVEC VALIDATION ===
        musique = participant.get('indicateurInedit', '')
        nb_courses = max(0, participant.get('nombreCourses', 0))
        nb_victoires = max(0, participant.get('nombreVictoires', 0))
        nb_places = max(0, participant.get('nombrePlaces', 0))
        gains = max(0, participant.get('gainsCarriere', 0))
        
        # Validation cohérence statistiques
        if nb_victoires > nb_places:
            logger.warning(f"#{numero} {nom}: victoires ({nb_victoires}) > places ({nb_places}), correction")
            nb_places = nb_victoires
        if nb_places > nb_courses:
            logger.warning(f"#{numero} {nom}: places ({nb_places}) > courses ({nb_courses}), correction")
            nb_courses = nb_places
        
        # === CHRONOS ===
        dernier_chrono = self._parse_chrono(participant.get('dernierRapportDirect', {}).get('tempsObtenu'))
        meilleur_chrono = self._parse_chrono(participant.get('recordTemps'))
        
        # === TACTIQUE ===
        deferre = participant.get('deferre', '0')
        specialite = discipline
        
        # === AVIS ===
        avis = participant.get('avisEntraineur', 'NEUTRE')
        
        # === COTE AVEC GESTION INTELLIGENTE ===
        cote_data = participant.get('rapportDirect', {})
        cote = cote_data.get('rapportProbable', 0.0)
        if cote <= 0 or cote == 0.0:
            # Cote manquante = marquer None plutôt que 99.0 arbitraire
            # Le scoring_engine gérera ce cas spécifiquement
            cote = None
            logger.debug(f"#{numero} {nom}: cote manquante")
        
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
            cote=cote if cote else 99.0  # Fallback pour compatibilité
        )
        
        return horse
    
    def _parse_chrono(self, chrono_str: Optional[str]) -> Optional[float]:
        """
        Parse un chrono format "1'14\"2" en secondes avec validation.
        
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
                
                # Validation cohérence (chrono trot = 1-3 min généralement)
                total_seconds = minutes * 60 + seconds
                if total_seconds < 60 or total_seconds > 300:
                    logger.warning(f"Chrono suspect: {total_seconds}s")
                
                return total_seconds
            
            return None
        except (ValueError, AttributeError):
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
            
            # Rapports réels PMU
            rapports = data.get('rapports', {})
            
            return {
                'arrivee': arrivee_finale,
                'non_partants': non_partants,
                'rapports': rapports
            }
            
        except Exception as e:
            logger.error(f"Erreur récupération résultats: {e}", exc_info=True)
            return None
    
    def clear_cache(self):
        """Vide le cache (utile pour tests ou si besoin données fraîches)."""
        self._cache.clear()
        logger.info("Cache scraper vidé")


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
