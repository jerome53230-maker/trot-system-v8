"""
PMU Scraper - Récupération données courses
Corrigé avec get_race_results()
"""

import requests
import json
from typing import Optional, Dict, List
from datetime import datetime
import time


class PMUScraper:
    """Scraper pour l'API PMU"""
    
    def __init__(self):
        self.base_url = "https://online.turfinfo.api.pmu.fr/rest/client/1"
        self.cache = {}
        self.cache_duration = 300  # 5 minutes
    
    def get_race_data(self, date_str: str, reunion: int, course: int) -> Optional[Dict]:
        """
        Récupère les données d'une course à venir.
        
        Args:
            date_str: Format DDMMYYYY
            reunion: Numéro réunion (1-9)
            course: Numéro course (1-16)
        
        Returns:
            Dict avec données de course
        """
        try:
            # Conversion date
            day = int(date_str[:2])
            month = int(date_str[2:4])
            year = int(date_str[4:8])
            formatted_date = f"{day:02d}{month:02d}{year}"
            
            # URL API PMU
            url = f"{self.base_url}/programme/{formatted_date}/R{reunion}/C{course}"
            
            print(f"📡 Récupération course: {url}")
            
            # Cache check
            cache_key = f"{formatted_date}_R{reunion}C{course}"
            if cache_key in self.cache:
                cache_time, data = self.cache[cache_key]
                if time.time() - cache_time < self.cache_duration:
                    print("✅ Données depuis cache")
                    return data
            
            # Requête API
            response = requests.get(url, timeout=10)
            
            if response.status_code == 404:
                print(f"❌ Course introuvable")
                return None
            
            if response.status_code != 200:
                print(f"❌ Erreur API: {response.status_code}")
                return None
            
            data = response.json()
            
            # Parse data
            race = {
                'date': f"{day:02d}/{month:02d}/{year}",
                'reunion': reunion,
                'course': course,
                'hippodrome': data.get('libelleCourt', 'INCONNU'),
                'distance': data.get('distance', 0),
                'discipline': data.get('discipline', 'TROT'),
                'montantPrix': data.get('montantPrix', 0),
                'participants': []
            }
            
            # Participants
            for participant in data.get('participants', []):
                cheval = {
                    'numero': participant.get('numPmu'),
                    'nom': participant.get('nom', 'INCONNU'),
                    'sexe': participant.get('sexe', ''),
                    'age': participant.get('age', 0),
                    'driver': participant.get('driver', 'N/A'),
                    'entraineur': participant.get('entraineur', 'N/A'),
                    'proprietaire': participant.get('proprietaire', 'N/A'),
                    'musique': participant.get('musique', ''),
                    'handicapDistance': participant.get('handicapDistance', 0),
                    'nombreCourses': participant.get('nombreCourses', 0),
                    'nombreVictoires': participant.get('nombreVictoires', 0),
                    'nombrePlaces': participant.get('nombrePlaces', 0),
                    'nombrePlacesSecond': participant.get('nombrePlacesSecond', 0),
                    'nombrePlacesTroisieme': participant.get('nombrePlacesTroisieme', 0),
                    'ordreArrivee': participant.get('ordreArrivee'),
                }
                
                # Cotes
                if 'rapportDirectReference' in participant:
                    cheval['cote'] = participant['rapportDirectReference'].get('rapport', 99.0)
                else:
                    cheval['cote'] = 99.0
                
                race['participants'].append(cheval)
            
            # Cache
            self.cache[cache_key] = (time.time(), race)
            
            print(f"✅ Course récupérée: {len(race['participants'])} partants")
            return race
            
        except requests.Timeout:
            print(f"❌ Timeout récupération course")
            return None
        except Exception as e:
            print(f"❌ Erreur inattendue: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_race_results(self, date_str: str, reunion: int, course: int) -> Optional[Dict]:
        """
        Récupère les résultats réels d'une course terminée.
        
        Args:
            date_str: Date format DDMMYYYY (ex: 18122025)
            reunion: Numéro réunion (1-9)
            course: Numéro course (1-16)
        
        Returns:
            Dict avec:
                - arrivee: List[int] - Ordre d'arrivée
                - non_partants: List[int] - Chevaux non-partants
                - rapports: Dict - Rapports PMU par type de pari
                - date: str - Date formatée
                - reunion: int
                - course: int
                - hippodrome: str
        """
        try:
            # Conversion date DDMMYYYY -> DDMMYYYY (API PMU format)
            day = int(date_str[:2])
            month = int(date_str[2:4])
            year = int(date_str[4:8])
            formatted_date = f"{day:02d}{month:02d}{year}"
            
            print(f"🔍 Récupération résultats: {formatted_date} R{reunion}C{course}")
            
            # ===== ÉTAPE 1: Arrivée définitive =====
            url_arrivee = (
                f"{self.base_url}/programme/"
                f"{formatted_date}/R{reunion}/C{course}/arrivee-definitive"
            )
            
            print(f"📡 Requête arrivée: {url_arrivee}")
            response_arrivee = requests.get(url_arrivee, timeout=10)
            
            if response_arrivee.status_code == 404:
                print("❌ Course non terminée ou introuvable")
                return None
            
            if response_arrivee.status_code != 200:
                print(f"❌ Erreur API arrivée: {response_arrivee.status_code}")
                return None
            
            arrivee_data = response_arrivee.json()
            
            # Extraction participants avec leur place
            participants = arrivee_data.get('participants', [])
            
            # Tri par place
            chevaux_classes = []
            for cheval in participants:
                place_info = cheval.get('place', {})
                place = place_info.get('place')
                status = place_info.get('statusArrivee', '')
                num_pmu = cheval.get('numPmu')
                
                if place and num_pmu:
                    chevaux_classes.append({
                        'numero': num_pmu,
                        'place': place,
                        'status': status
                    })
            
            # Trier par place
            chevaux_classes.sort(key=lambda x: x['place'])
            arrivee = [c['numero'] for c in chevaux_classes]
            
            # Non-partants
            non_partants = [
                c['numPmu'] for c in participants
                if c.get('place', {}).get('statusArrivee') == 'NON_PARTANT'
            ]
            
            print(f"✅ Arrivée: {'-'.join(map(str, arrivee[:5]))}")
            if non_partants:
                print(f"🚫 Non-partants: {non_partants}")
            
            # ===== ÉTAPE 2: Rapports définitifs =====
            url_rapports = (
                f"{self.base_url}/programme/"
                f"{formatted_date}/R{reunion}/C{course}/rapports-definitifs"
            )
            
            print(f"📡 Requête rapports: {url_rapports}")
            response_rapports = requests.get(url_rapports, timeout=10)
            
            if response_rapports.status_code != 200:
                print(f"⚠️ Rapports non disponibles (code {response_rapports.status_code})")
                rapports_pmu = {}
            else:
                rapports_raw = response_rapports.json()
                rapports_pmu = self._parse_rapports_pmu(rapports_raw)
                print(f"✅ Rapports récupérés: {len(rapports_pmu)} types de paris")
            
            # Résultat final
            results = {
                'arrivee': arrivee,
                'non_partants': non_partants,
                'rapports': rapports_pmu,
                'date': f"{day:02d}/{month:02d}/{year}",
                'reunion': reunion,
                'course': course,
                'hippodrome': arrivee_data.get('libelleCourt', 'INCONNU')
            }
            
            return results
            
        except requests.Timeout:
            print(f"❌ Timeout récupération résultats")
            return None
        except requests.RequestException as e:
            print(f"❌ Erreur réseau: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur inattendue: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_rapports_pmu(self, rapports_raw: List[Dict]) -> Dict:
        """
        Parse les rapports PMU bruts en structure exploitable.
        
        Args:
            rapports_raw: Liste des rapports bruts de l'API PMU
        
        Returns:
            Dict avec rapports par type de pari:
            {
                'SIMPLE_GAGNANT': [
                    {'combinaison': '7', 'dividende': 2.3, 'libelle': 'Simple gagnant'}
                ],
                ...
            }
        """
        rapports = {}
        
        for pari in rapports_raw:
            type_pari = pari.get('typePari')
            if not type_pari:
                continue
            
            rapports[type_pari] = []
            
            for rapport in pari.get('rapports', []):
                combinaison = rapport.get('combinaison', '')
                dividende = rapport.get('dividendePourUnEuro', 0)
                
                # Ignorer les non-partants et dividendes nuls
                if dividende > 0 and 'NP' not in combinaison:
                    rapports[type_pari].append({
                        'combinaison': combinaison,
                        'dividende': dividende / 100,  # Conversion centimes -> euros
                        'libelle': rapport.get('libelle', ''),
                        'nombre_gagnants': rapport.get('nombreGagnants', 0)
                    })
        
        return rapports


# Test
if __name__ == "__main__":
    scraper = PMUScraper()
    
    print("\n" + "="*60)
    print("TEST 1: Récupération données course")
    print("="*60)
    race = scraper.get_race_data('18122025', 1, 1)
    if race:
        print(f"✅ {race['hippodrome']} - {len(race['participants'])} partants")
    
    print("\n" + "="*60)
    print("TEST 2: Récupération résultats")
    print("="*60)
    results = scraper.get_race_results('18122025', 1, 1)
    if results:
        print(f"✅ Arrivée: {results['arrivee']}")
        print(f"✅ Rapports: {len(results['rapports'])} types")
