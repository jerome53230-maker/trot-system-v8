#!/usr/bin/env python3
"""
Script de diagnostic complet pour l'API PMU
Teste tous les endpoints et formats possibles
"""

import requests
import json
from datetime import datetime

# Configuration
DATE = "17122025"
REUNION = 1
COURSE = 8

BASE_URL = "https://online.turfinfo.api.pmu.fr/rest/client/1"

print("=" * 80)
print(f"DIAGNOSTIC API PMU - {DATE} R{REUNION}C{COURSE}")
print("=" * 80)
print()

# Test 1: Endpoint programme principal
print("TEST 1: Endpoint Programme Principal")
print("-" * 80)
url1 = f"{BASE_URL}/programme/{DATE}/R{REUNION}/C{COURSE}"
print(f"URL: {url1}")

try:
    r1 = requests.get(url1, timeout=15)
    print(f"Status: {r1.status_code}")
    
    if r1.status_code == 200:
        data1 = r1.json()
        print(f"Type réponse: {type(data1)}")
        
        if isinstance(data1, dict):
            print(f"Clés principales: {list(data1.keys())[:10]}")
            
            # Vérifier participants
            if 'participants' in data1:
                part = data1['participants']
                print(f"\n✓ 'participants' trouvé !")
                print(f"  Type: {type(part)}")
                
                if isinstance(part, list):
                    print(f"  Longueur: {len(part)}")
                    if len(part) > 0:
                        first = part[0]
                        print(f"  Premier élément type: {type(first)}")
                        if isinstance(first, dict):
                            print(f"  ✅ FORMAT CORRECT - Dict avec clés: {list(first.keys())[:5]}")
                            print(f"  Exemple: numPmu={first.get('numPmu')}, nom={first.get('nom')}")
                        elif isinstance(first, str):
                            print(f"  ❌ PROBLÈME - String: '{first}'")
                        else:
                            print(f"  ❌ Format inconnu: {first}")
                elif isinstance(part, dict):
                    print(f"  Clés dans dict: {list(part.keys())}")
            else:
                print("\n⚠️ Pas de 'participants' dans réponse principale")
        
except Exception as e:
    print(f"❌ Erreur: {e}")

print("\n")

# Test 2: Endpoint participants séparé
print("TEST 2: Endpoint Participants Séparé")
print("-" * 80)
url2 = f"{BASE_URL}/programme/{DATE}/R{REUNION}/C{COURSE}/participants"
print(f"URL: {url2}")

try:
    r2 = requests.get(url2, timeout=15)
    print(f"Status: {r2.status_code}")
    
    if r2.status_code == 200:
        data2 = r2.json()
        print(f"Type réponse: {type(data2)}")
        
        if isinstance(data2, list):
            print(f"✓ Liste directe - Longueur: {len(data2)}")
            if len(data2) > 0:
                first = data2[0]
                print(f"  Premier élément type: {type(first)}")
                if isinstance(first, dict):
                    print(f"  ✅ FORMAT CORRECT - Clés: {list(first.keys())[:5]}")
                    print(f"  Exemple: numPmu={first.get('numPmu')}, nom={first.get('nom')}")
                else:
                    print(f"  ❌ PROBLÈME - {type(first)}: {first}")
        
        elif isinstance(data2, dict):
            print(f"✓ Dict - Clés: {list(data2.keys())}")
            
            # Chercher participants dans le dict
            for key in ['participants', 'participant', 'partants', 'chevaux']:
                if key in data2:
                    part = data2[key]
                    print(f"\n✓ Trouvé sous '{key}'")
                    print(f"  Type: {type(part)}")
                    if isinstance(part, list) and len(part) > 0:
                        first = part[0]
                        print(f"  Premier élément: {type(first)}")
                        if isinstance(first, dict):
                            print(f"  ✅ FORMAT CORRECT")
                            print(f"  Clés: {list(first.keys())[:5]}")
                        else:
                            print(f"  ❌ PROBLÈME: {first}")
                    break
                    
except Exception as e:
    print(f"❌ Erreur: {e}")

print("\n")

# Test 3: Performances détaillées
print("TEST 3: Endpoint Performances Détaillées")
print("-" * 80)
url3 = f"{BASE_URL}/programme/{DATE}/R{REUNION}/C{COURSE}/performances-detaillees/pretty"
print(f"URL: {url3}")

try:
    r3 = requests.get(url3, timeout=15)
    print(f"Status: {r3.status_code}")
    
    if r3.status_code == 200:
        data3 = r3.json()
        print(f"Type réponse: {type(data3)}")
        if isinstance(data3, dict):
            print(f"Clés: {list(data3.keys())[:10]}")
            
            for key in ['participants', 'performances', 'chevaux', 'partants']:
                if key in data3:
                    print(f"\n✓ Trouvé sous '{key}'")
                    part = data3[key]
                    if isinstance(part, list) and len(part) > 0:
                        first = part[0]
                        print(f"  Type premier: {type(first)}")
                        if isinstance(first, dict):
                            print(f"  ✅ UTILISABLE")
                        break
                        
except Exception as e:
    print(f"❌ Erreur: {e}")

print("\n")
print("=" * 80)
print("CONCLUSION")
print("=" * 80)
print("\n✓ Utilisez ce diagnostic pour identifier quel endpoint fonctionne")
print("✓ Si strings détectées, l'endpoint est incorrect")
print("✓ Si dicts détectés, l'endpoint est correct")
print()
