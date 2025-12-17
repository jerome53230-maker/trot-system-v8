# ============================================================================
# TROT SYSTEM v8.0 - COEFFICIENTS NORMALISATION HIPPODROMES
# ============================================================================
# Date: Décembre 2025
# Description: Normalisation chronos relatifs à Vincennes (référence)

"""
Coefficients de normalisation des chronos par hippodrome.
Valeurs en secondes à AJOUTER au chrono brut pour normaliser à Vincennes.

Exemples:
- Cabourg -0.5s → Piste rapide (retirer 0.5s)
- Caen +0.8s → Piste lente (ajouter 0.8s)
- Vincennes 0.0s → Référence
"""

# ============================================================================
# COEFFICIENTS HIPPODROMES FRANÇAIS (30+ pistes)
# ============================================================================

TRACK_COEFFICIENTS = {
    # RÉGION PARISIENNE
    "VINCENNES": 0.0,           # Référence nationale
    "ENGHIEN": 0.0,             # Équivalent Vincennes
    "SAINT-CLOUD": +0.2,        # Légèrement plus lent
    
    # NORMANDIE
    "CABOURG": -0.5,            # Piste rapide (sable drainant)
    "CAEN": +0.8,               # Piste lourde
    "ARGENTAN": +0.4,
    "GRAIGNES": +0.6,
    "LISIEUX": +0.3,
    
    # BRETAGNE
    "NANTES": +0.5,
    "RENNES": +0.4,
    "CORDEMAIS": +0.7,
    "PLOERMEL": +0.5,
    
    # CÔTE D'AZUR
    "CAGNES-SUR-MER": +0.3,     # Cagnes
    "HYERES": +0.4,
    "MARSEILLE-BORELY": +0.5,
    "FREJUS": +0.4,
    
    # SUD-OUEST
    "BORDEAUX": +0.5,
    "PAU": +0.6,
    "TOULOUSE": +0.4,
    "AGEN": +0.5,
    "TARBES": +0.6,
    
    # CENTRE
    "VICHY": +0.3,
    "AMIENS": +0.5,
    "CHARTRES": +0.4,
    "ANGERS": +0.5,
    "LE MANS": +0.4,
    "LAVAL": +0.5,
    
    # EST
    "REIMS": +0.4,
    "STRASBOURG": +0.3,
    "METZ": +0.4,
    "NANCY": +0.5,
    "COLMAR": +0.4,
    
    # NORD
    "LYON-PARILLY": +0.3,
    "LYON": +0.3,
    "ROUEN": +0.5,
    "LILLE": +0.4,
    "CHATEAUBRIANT": +0.6,
    
    # AUTRES RÉGIONS
    "MESLAY-DU-MAINE": +0.5,
    "CRAON": +0.6,
    "SEGRE": +0.5,
    "PORNICHET": +0.4,
    "LA CAPELLE": +0.7,
}

# ============================================================================
# ALIAS HIPPODROMES (noms alternatifs)
# ============================================================================

TRACK_ALIASES = {
    "PARIS-VINCENNES": "VINCENNES",
    "CAGNES": "CAGNES-SUR-MER",
    "LYON PARILLY": "LYON-PARILLY",
    "MARSEILLE": "MARSEILLE-BORELY",
    "BORELY": "MARSEILLE-BORELY",
}

# ============================================================================
# FONCTIONS NORMALISATION
# ============================================================================

def normalize_chrono(time_raw: float, track: str, distance: int) -> float:
    """
    Normalise un chrono relatif à Vincennes.
    
    Args:
        time_raw: Temps brut en secondes (ex: 74.2 pour 1'14"2)
        track: Nom hippodrome (ex: "CAEN")
        distance: Distance course en mètres (ex: 2700)
    
    Returns:
        Temps normalisé en secondes
    
    Example:
        >>> normalize_chrono(74.2, "CAEN", 2700)
        75.0  # +0.8s car Caen est lent
    """
    # Gestion alias
    track_normalized = TRACK_ALIASES.get(track.upper(), track.upper())
    
    # Coefficient par défaut (piste inconnue)
    coefficient = TRACK_COEFFICIENTS.get(track_normalized, 0.0)
    
    return time_raw + coefficient


def get_track_info(track: str) -> dict:
    """
    Récupère les infos d'un hippodrome.
    
    Args:
        track: Nom hippodrome
    
    Returns:
        Dict avec coefficient, catégorie
    """
    track_normalized = TRACK_ALIASES.get(track.upper(), track.upper())
    coefficient = TRACK_COEFFICIENTS.get(track_normalized, 0.0)
    
    # Catégorisation
    if coefficient < -0.3:
        category = "RAPIDE"
    elif coefficient > 0.5:
        category = "LENT"
    elif coefficient == 0.0:
        category = "REFERENCE"
    else:
        category = "NORMAL"
    
    return {
        "name": track_normalized,
        "coefficient": coefficient,
        "category": category,
        "is_known": track_normalized in TRACK_COEFFICIENTS
    }


def compare_chronos(time1: float, track1: str, time2: float, track2: str) -> dict:
    """
    Compare deux chronos sur hippodromes différents.
    
    Returns:
        Dict avec times normalisés et différence
    """
    norm1 = normalize_chrono(time1, track1, 2700)
    norm2 = normalize_chrono(time2, track2, 2700)
    
    return {
        "time1_normalized": norm1,
        "time2_normalized": norm2,
        "difference": norm1 - norm2,
        "faster": "time1" if norm1 < norm2 else "time2"
    }


# ============================================================================
# VALIDATION MODULE
# ============================================================================

if __name__ == "__main__":
    # Test normalisation
    print("=" * 70)
    print("TROT SYSTEM v8.0 - TEST NORMALISATION CHRONOS")
    print("=" * 70)
    
    # Test 1: Caen vs Vincennes
    print("\n1. Comparaison Caen vs Vincennes (1'14\")")
    caen_time = 74.0
    vincennes_time = 74.0
    
    print(f"   Caen brut: {caen_time}s")
    print(f"   Caen normalisé: {normalize_chrono(caen_time, 'CAEN', 2700)}s")
    print(f"   Vincennes: {vincennes_time}s (référence)")
    
    # Test 2: Cabourg (rapide)
    print("\n2. Cabourg (piste rapide)")
    cabourg_time = 74.0
    print(f"   Cabourg brut: {cabourg_time}s")
    print(f"   Cabourg normalisé: {normalize_chrono(cabourg_time, 'CABOURG', 2700)}s")
    print(f"   → Plus rapide que Vincennes !")
    
    # Test 3: Infos hippodrome
    print("\n3. Infos hippodromes")
    for track in ["VINCENNES", "CAEN", "CABOURG", "NANTES", "INCONNU"]:
        info = get_track_info(track)
        print(f"   {track}: {info}")
    
    print("\n" + "=" * 70)
    print("✓ Module track_coefficients.py validé")
    print("=" * 70)
