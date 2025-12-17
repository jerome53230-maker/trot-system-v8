# ============================================================================
# TROT SYSTEM v8.0 - TESTS UNITAIRES
# ============================================================================

"""
Tests unitaires pour le scraper et validation données.

Usage:
    python -m pytest tests/test_scraper.py -v
    python -m pytest tests/test_scraper.py -v --cov=core
"""

import pytest
from datetime import datetime
from core.scraper import PMUScraper
from unittest.mock import Mock, patch, MagicMock


class TestPMUScraper:
    """Tests pour la classe PMUScraper."""
    
    def test_init(self):
        """Test initialisation scraper."""
        scraper = PMUScraper()
        assert scraper.BASE_URL == "https://online.turfinfo.api.pmu.fr/rest/client/1"
        assert scraper.session is not None
        assert isinstance(scraper._cache, dict)
    
    def test_parse_chrono_valid(self):
        """Test parsing chronos valides."""
        scraper = PMUScraper()
        
        # Format 1'14"2
        assert scraper._parse_chrono("1'14\"2") == 74.2
        assert scraper._parse_chrono("1'14.2") == 74.2
        
        # Format 2'00
        assert scraper._parse_chrono("2'00") == 120.0
        
        # Format 1'30"5
        assert scraper._parse_chrono("1'30\"5") == 90.5
    
    def test_parse_chrono_invalid(self):
        """Test parsing chronos invalides."""
        scraper = PMUScraper()
        
        assert scraper._parse_chrono(None) is None
        assert scraper._parse_chrono("") is None
        assert scraper._parse_chrono("invalid") is None
        assert scraper._parse_chrono("abc") is None
    
    def test_parse_chrono_edge_cases(self):
        """Test cas limites chronos."""
        scraper = PMUScraper()
        
        # Chrono suspect (trop rapide)
        result = scraper._parse_chrono("0'30")
        assert result == 30.0  # Accepté mais warning loggé
        
        # Chrono suspect (trop lent)
        result = scraper._parse_chrono("5'30")
        assert result == 330.0  # Accepté mais warning loggé
    
    @patch('core.scraper.requests.Session')
    def test_fetch_json_404(self, mock_session_class):
        """Test comportement sur ressource inexistante (404)."""
        # Mock session
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        scraper = PMUScraper()
        scraper.session = mock_session
        
        result = scraper._fetch_json("http://test.com/404")
        
        assert result is None
        mock_session.get.assert_called_once()
    
    @patch('core.scraper.requests.Session')
    def test_fetch_json_503_retry(self, mock_session_class):
        """Test retry automatique sur erreur temporaire (503)."""
        mock_session = Mock()
        
        # Première tentative: 503
        mock_response_503 = Mock()
        mock_response_503.status_code = 503
        
        # Deuxième tentative: succès
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"data": "success"}
        
        mock_session.get.side_effect = [mock_response_503, mock_response_200]
        mock_session_class.return_value = mock_session
        
        scraper = PMUScraper()
        scraper.session = mock_session
        
        result = scraper._fetch_json("http://test.com/503", retry_count=1)
        
        assert result == {"data": "success"}
        assert mock_session.get.call_count == 2
    
    def test_build_horse_validation_numero_invalide(self):
        """Test validation numéro cheval invalide."""
        scraper = PMUScraper()
        
        participant = {
            'numPmu': 0,  # Invalide
            'nom': 'Test Horse'
        }
        
        with pytest.raises(ValueError, match="Numéro cheval invalide"):
            scraper._build_horse(participant, 'ATTELE', 'VINCENNES')
    
    def test_build_horse_validation_nom_manquant(self):
        """Test validation nom cheval manquant."""
        scraper = PMUScraper()
        
        participant = {
            'numPmu': 1,
            'nom': ''  # Vide
        }
        
        with pytest.raises(ValueError, match="Nom cheval manquant"):
            scraper._build_horse(participant, 'ATTELE', 'VINCENNES')
    
    def test_build_horse_coherence_statistiques(self):
        """Test correction automatique statistiques incohérentes."""
        scraper = PMUScraper()
        
        participant = {
            'numPmu': 1,
            'nom': 'Test Horse',
            'nombreCourses': 10,
            'nombreVictoires': 5,
            'nombrePlaces': 3  # Incohérent: victoires > places
        }
        
        horse = scraper._build_horse(participant, 'ATTELE', 'VINCENNES')
        
        # Doit corriger: places = victoires
        assert horse.nb_places == 5
        assert horse.nb_victoires == 5
        assert horse.nb_courses == 10
    
    def test_build_horse_cote_manquante(self):
        """Test gestion cote manquante."""
        scraper = PMUScraper()
        
        participant = {
            'numPmu': 1,
            'nom': 'Test Horse',
            'rapportDirect': {
                'rapportProbable': 0.0  # Cote manquante
            }
        }
        
        horse = scraper._build_horse(participant, 'ATTELE', 'VINCENNES')
        
        # Doit fallback à 99.0
        assert horse.cote == 99.0
    
    def test_cache_functionality(self):
        """Test fonctionnement du cache."""
        scraper = PMUScraper()
        
        # Cache vide au départ
        assert len(scraper._cache) == 0
        
        # Simuler ajout cache
        from datetime import datetime
        test_race = Mock()
        cache_key = "16122025_R1C1"
        scraper._cache[cache_key] = (test_race, datetime.now())
        
        assert cache_key in scraper._cache
        
        # Clear cache
        scraper.clear_cache()
        assert len(scraper._cache) == 0
    
    def test_extract_discipline(self):
        """Test extraction discipline."""
        scraper = PMUScraper()
        
        # Attelé
        assert scraper._extract_discipline({'specialite': 'ATTELE'}) == 'ATTELE'
        assert scraper._extract_discipline({'specialite': 'attele'}) == 'ATTELE'
        
        # Monté
        assert scraper._extract_discipline({'specialite': 'MONTE'}) == 'MONTE'
        assert scraper._extract_discipline({'specialite': 'monté'}) == 'MONTE'
        
        # Défaut
        assert scraper._extract_discipline({'specialite': ''}) == 'ATTELE'
        assert scraper._extract_discipline({}) == 'ATTELE'


class TestHistoriquePersistant:
    """Tests pour la persistance historique."""
    
    def test_history_file_path(self):
        """Test chemin fichier historique."""
        from pathlib import Path
        from app import HISTORY_FILE
        
        assert isinstance(HISTORY_FILE, Path)
        assert HISTORY_FILE.name == "history.json"
        assert "data" in str(HISTORY_FILE)
    
    @patch('builtins.open', create=True)
    @patch('json.load')
    def test_load_history_success(self, mock_json_load, mock_open):
        """Test chargement historique réussi."""
        from app import load_history
        
        mock_data = [
            {"date": "16122025", "reunion": 1, "course": 1},
            {"date": "17122025", "reunion": 2, "course": 3}
        ]
        mock_json_load.return_value = mock_data
        
        # Simuler fichier existant
        with patch('pathlib.Path.exists', return_value=True):
            result = load_history()
        
        assert result == mock_data
        assert len(result) == 2
    
    @patch('builtins.open', create=True)
    @patch('json.dump')
    def test_save_history_success(self, mock_json_dump, mock_open):
        """Test sauvegarde historique réussie."""
        from app import save_history
        
        test_history = [
            {"date": "16122025", "reunion": 1, "course": 1}
        ]
        
        save_history(test_history)
        
        mock_json_dump.assert_called_once()


# ============================================================================
# FIXTURES PYTEST
# ============================================================================

@pytest.fixture
def sample_participant():
    """Fixture participant PMU valide."""
    return {
        'numPmu': 7,
        'nom': 'ECLAIR DU BOURG',
        'driver': {'nom': 'Jean DUPONT'},
        'entraineur': {'nom': 'Pierre MARTIN'},
        'proprietaire': {'nom': 'Ecurie Test'},
        'indicateurInedit': '1a2a4a',
        'nombreCourses': 20,
        'nombreVictoires': 5,
        'nombrePlaces': 12,
        'gainsCarriere': 50000,
        'dernierRapportDirect': {'tempsObtenu': "1'14\"2"},
        'recordTemps': "1'12\"5",
        'deferre': '0',
        'avisEntraineur': 'BON',
        'rapportDirect': {'rapportProbable': 3.2}
    }


@pytest.fixture
def scraper():
    """Fixture scraper PMU."""
    return PMUScraper()


# ============================================================================
# TESTS AVEC FIXTURES
# ============================================================================

def test_build_horse_with_valid_data(scraper, sample_participant):
    """Test construction cheval avec données valides."""
    horse = scraper._build_horse(sample_participant, 'ATTELE', 'VINCENNES')
    
    assert horse.numero == 7
    assert horse.nom == 'ECLAIR DU BOURG'
    assert horse.driver == 'Jean DUPONT'
    assert horse.nb_courses == 20
    assert horse.cote == 3.2
    assert horse.dernier_chrono == 74.2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
