# 🚀 Guide Démarrage Rapide - Trot System v8.0

## ⚡ En 5 Minutes

### 1️⃣ Obtenir Clé API Gemini (2 min)

1. Ouvrir navigateur : https://aistudio.google.com
2. Se connecter avec compte Google/Gmail
3. Cliquer **"Get API key"**
4. Cliquer **"Create API key"**
5. **COPIER** la clé (format `AIzaSyD...`)

### 2️⃣ Configuration Locale (1 min)

```bash
# Clone repository
git clone https://github.com/your-username/trot-system-v8.git
cd trot-system-v8

# Créer fichier .env
echo "GEMINI_API_KEY=your_api_key_here" > .env

# Installer dépendances
pip install -r requirements.txt
```

### 3️⃣ Test Local (1 min)

```bash
# Démarrer serveur
python app.py

# Dans un autre terminal, tester
curl "http://localhost:5000/race?date=15122025&r=1&c=4&budget=20"
```

### 4️⃣ Déploiement Render (1 min)

1. **GitHub** : Push code
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Render Dashboard** : https://dashboard.render.com
   - New → Web Service
   - Connecter repo GitHub
   - Build : `pip install -r requirements.txt`
   - Start : `gunicorn app:app`
   - Env var : `GEMINI_API_KEY` = `your_key`

3. **Deploy** → Attendre 2 min ✅

---

## 📱 Utilisation Mobile

### iPhone/Android

1. **Safari/Chrome** → URL :
   ```
   https://your-app.onrender.com/race?date=15122025&r=1&c=4&budget=20
   ```

2. **Ajouter à l'écran d'accueil** :
   - Safari : Partager → Sur l'écran d'accueil
   - Chrome : Menu → Ajouter à l'écran d'accueil

3. **Lancer analyse** → Copier paris → App PMU ✅

---

## 🎯 Exemples Requêtes

### Analyse Course Aujourd'hui
```bash
# Paris Vincennes R1C4 avec 20€
curl "https://your-app.onrender.com/race?date=16122025&r=1&c=4&budget=20"
```

### Budget Réduit (10€)
```bash
curl "https://your-app.onrender.com/race?date=16122025&r=1&c=4&budget=10"
```

### Débriefing Post-Course
```bash
curl "https://your-app.onrender.com/debrief?date=15122025&r=1&c=4"
```

### Historique
```bash
curl "https://your-app.onrender.com/history?limit=20"
```

---

## ⚠️ Troubleshooting

### Erreur "GEMINI_API_KEY manquante"
→ Vérifier variable environnement Render ou fichier .env local

### Erreur "Course introuvable"
→ Vérifier date au format `DDMMYYYY` et numéros R/C valides

### Réponse lente (>10s)
→ Normal pour Gemini, retry automatique activé

### Erreur 429 "Rate limit"
→ Quota Gemini atteint (15 req/min), attendre 1 minute

---

## 📊 Scénarios Typiques

### CADENAS (60% des courses)
- **Exemple** : Favori 88/100, écart 15 pts avec 2ème
- **Paris** : SIMPLE_GAGNANT (60%) + COUPLE_PLACE (40%)

### BATAILLE (25%)
- **Exemple** : 6 chevaux entre 70-80 pts
- **Paris** : MULTI_4 (40%) + TRIO (30%) + Couples (30%)

### SURPRISE (10%)
- **Exemple** : Outsider cote 18, edge 15%, score 72
- **Paris** : SIMPLE_PLACE outsider (30%) + sécurité (70%)

### PIÈGE (5%)
- **Exemple** : Favori cote 2.5, score 62
- **Paris** : Éviter favori, jouer outsiders ≥70

---

## 💡 Conseils Pro

1. **Analyser 1h avant course** (données fraîches)
2. **Vérifier confiance_globale** (≥7/10 optimal)
3. **Suivre value_bets** détectés (edge ≥15%)
4. **Adapter budget** selon bankroll (recommandé 2-3% bankroll)
5. **Faire débriefing** systématique (amélioration continue)

---

## 🎓 Ressources

- **README complet** : `README.md`
- **Documentation API** : `docs/API_DOCS.md`
- **Architecture** : `docs/ARCHITECTURE.md`
- **Changelog** : `CHANGELOG.md`

---

**Support** : GitHub Issues ou your-email@example.com  
**Version** : 8.0.0  
**Dernière mise à jour** : 16/12/2025
