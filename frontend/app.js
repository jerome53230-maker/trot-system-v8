// ============================================================================
// TROT SYSTEM v8 - FRONTEND APPLICATION
// ============================================================================

// Gestion d'erreurs globale
window.addEventListener('error', function(event) {
    console.error('Erreur globale capturée:', event.error);
    const errorMsg = event.error?.message || 'Une erreur est survenue';
    if (!document.getElementById('error').classList.contains('hidden')) {
        // Une erreur est déjà affichée
        return;
    }
    showError(`Erreur: ${errorMsg}`);
});

// Configuration
const CONFIG = {
    API_URL: 'https://trot-system-v8.onrender.com',
    STORAGE_KEY: 'trot_history',
    MAX_HISTORY: 10
};

// État global
const state = {
    currentAnalysis: null,
    history: []
};

// ============================================================================
// INITIALISATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🐴 Trot System v8 - Frontend chargé');
    
    // Charger historique
    loadHistory();
    
    // Vérifier status API
    checkAPIStatus();
    
    // Event listeners
    setupEventListeners();
    
    // Pré-remplir date du jour
    fillTodayDate();
});

// ============================================================================
// EVENT LISTENERS
// ============================================================================

function setupEventListeners() {
    // Formulaire
    document.getElementById('raceForm').addEventListener('submit', handleFormSubmit);
    
    // Bouton effacer
    document.getElementById('clearBtn').addEventListener('click', clearForm);
    
    // Nouvelle analyse
    document.getElementById('newAnalysisBtn')?.addEventListener('click', () => {
        scrollToTop();
        clearForm();
        document.getElementById('results').classList.add('hidden');
    });
    
    // Débriefing
    document.getElementById('debrieBtn')?.addEventListener('click', handleDebriefing);
}

// ============================================================================
// GESTION FORMULAIRE
// ============================================================================

async function handleFormSubmit(e) {
    e.preventDefault();
    
    // Récupérer données
    const formData = {
        date: document.getElementById('date').value.trim(),
        reunion: parseInt(document.getElementById('reunion').value),
        course: parseInt(document.getElementById('course').value),
        budget: parseInt(document.getElementById('budget').value)
    };
    
    // Validation
    if (!validateForm(formData)) {
        return;
    }
    
    // Lancer analyse
    await analyzeRace(formData);
}

function validateForm(data) {
    // Date
    if (!/^\d{8}$/.test(data.date)) {
        showError('Format de date invalide. Utilisez JJMMAAAA (ex: 18122025)');
        return false;
    }
    
    // Réunion
    if (data.reunion < 1 || data.reunion > 9) {
        showError('La réunion doit être entre 1 et 9');
        return false;
    }
    
    // Course
    if (data.course < 1 || data.course > 16) {
        showError('La course doit être entre 1 et 16');
        return false;
    }
    
    return true;
}

function clearForm() {
    document.getElementById('raceForm').reset();
    fillTodayDate();
    hideError();
}

function fillTodayDate() {
    const today = new Date();
    const day = String(today.getDate()).padStart(2, '0');
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const year = today.getFullYear();
    document.getElementById('date').value = `${day}${month}${year}`;
}

// ============================================================================
// APPEL API - ANALYSE
// ============================================================================

async function analyzeRace(data) {
    // Afficher loading
    showLoading();
    hideError();
    document.getElementById('results').classList.add('hidden');
    
    try {
        // Construire URL
        const url = `${CONFIG.API_URL}/race?date=${data.date}&r=${data.reunion}&c=${data.course}&budget=${data.budget}`;
        
        console.log('📡 Appel API:', url);
        
        // Appel API
        const response = await fetch(url);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `Erreur ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        console.log('✅ Réponse API:', result);
        
        // Sauvegarder
        state.currentAnalysis = { ...result, ...data };
        
        // Afficher résultats
        displayResults(result, data);
        
        // Scroll vers résultats
        setTimeout(() => {
            document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
        }, 300);
        
    } catch (error) {
        console.error('❌ Erreur:', error);
        showError(error.message);
    } finally {
        hideLoading();
    }
}

// ============================================================================
// AFFICHAGE RÉSULTATS
// ============================================================================

function displayResults(data, formData) {
    console.log('═══════════════════════════════════════');
    console.log('🔍 DISPLAY RESULTS - DÉBUT');
    console.log('📦 Données reçues:', JSON.stringify(data, null, 2));
    console.log('📋 Form data:', formData);
    console.log('═══════════════════════════════════════');
    
    try {
        // Sauvegarder l'analyse complète dans state pour analyse détaillée
        state.currentAnalysis = {
            date: formData.date,
            reunion: formData.reunion,
            course: formData.course,
            data: data
        };
        
        // Info course
        const budgetUtilise = data.budget_utilise || 0;
        const roiMoyen = data.roi_moyen_attendu || 0;
        const infoText = `${formData.date} - Réunion ${formData.reunion} - Course ${formData.course} - Budget: ${budgetUtilise}€/${formData.budget}€ - ROI: ${roiMoyen}x`;
        document.getElementById('raceInfo').textContent = infoText;
        
        // Scénario
        console.log('📊 Affichage scénario...');
        displayScenario(data);
        
        // Conseil final (après scénario)
        if (data.conseil_final) {
            const scenarioCard = document.getElementById('scenarioCard');
            const conseilDiv = document.createElement('div');
            conseilDiv.className = 'mt-6 p-4 bg-white/10 rounded-lg';
            conseilDiv.innerHTML = `
                <div class="text-sm font-medium mb-2">💡 Conseil</div>
                <div class="text-sm opacity-90">${data.conseil_final}</div>
            `;
            scenarioCard.appendChild(conseilDiv);
        }
        
        // Top 5
        console.log('🏆 Affichage top 5...');
        displayTop5(data.top_5_chevaux || data.top5_chevaux || []);
        
        // Paris
        console.log('💰 Affichage paris...');
        console.log('Paris reçus:', data.paris_recommandes);
        displayParis(data.paris_recommandes || [], formData.budget);
        
        // Value Bets
        console.log('💎 Affichage value bets...');
        displayValueBets(data.value_bets_detectes || data.value_bets || []);
        
        // Raisonnement
        console.log('🤖 Affichage raisonnement...');
        displayRaisonnement(data.analyse_tactique || data.raisonnement || 'Aucune analyse disponible');
        
        // Sauvegarder dans l'historique
        saveToHistory(formData, data);
        saveToLocalStorage(formData, data);
        
        // Afficher
        document.getElementById('results').classList.remove('hidden');
        
        console.log('✅ DISPLAY RESULTS - SUCCÈS');
        console.log('═══════════════════════════════════════');
    } catch (error) {
        console.error('❌ ERREUR CRITIQUE displayResults:', error);
        console.error('Stack trace:', error.stack);
        showError(`Erreur d'affichage: ${error.message}`);
    }
}

function displayScenario(data) {
    const scenario = data.scenario_course || 'INCONNU';
    const confidence = data.confiance_globale || 0;
    const nbChevaux = data.nb_partants || 0;
    
    // Configuration scénarios
    const scenarios = {
        'CADENAS': {
            emoji: '🔒',
            title: 'CADENAS',
            subtitle: 'Favori très dominant',
            colors: 'bg-gradient-to-br from-green-600 to-green-800'
        },
        'BATAILLE': {
            emoji: '⚔️',
            title: 'BATAILLE',
            subtitle: 'Course ouverte et disputée',
            colors: 'bg-gradient-to-br from-yellow-600 to-orange-600'
        },
        'SURPRISE': {
            emoji: '🎲',
            title: 'SURPRISE',
            subtitle: 'Outsider peut gagner',
            colors: 'bg-gradient-to-br from-orange-600 to-red-600'
        },
        'PIEGE': {
            emoji: '🚫',
            title: 'PIÈGE',
            subtitle: 'Favori surestimé',
            colors: 'bg-gradient-to-br from-red-600 to-red-800'
        },
        'NON_JOUABLE': {
            emoji: '⛔',
            title: 'NON JOUABLE',
            subtitle: 'Course trop incertaine',
            colors: 'bg-gradient-to-br from-gray-600 to-gray-800'
        }
    };
    
    const config = scenarios[scenario] || scenarios['NON_JOUABLE'];
    
    const card = document.getElementById('scenarioCard');
    // Nettoyer le contenu existant pour éviter les doublons
    card.innerHTML = `
        <div class="text-6xl mb-4" id="scenarioEmoji"></div>
        <h3 class="text-4xl font-bold mb-2" id="scenarioTitle"></h3>
        <p class="text-xl opacity-90" id="scenarioSubtitle"></p>
        <div class="mt-6 flex justify-center gap-8">
            <div>
                <div class="text-3xl font-bold" id="confidence"></div>
                <div class="text-sm opacity-75">Confiance</div>
            </div>
            ${nbChevaux > 0 ? `
            <div>
                <div class="text-3xl font-bold" id="nbChevaux"></div>
                <div class="text-sm opacity-75">Partants</div>
            </div>
            ` : ''}
        </div>
    `;
    card.className = `rounded-2xl shadow-2xl p-8 text-center card-hover ${config.colors}`;
    
    document.getElementById('scenarioEmoji').textContent = config.emoji;
    document.getElementById('scenarioTitle').textContent = config.title;
    document.getElementById('scenarioSubtitle').textContent = config.subtitle;
    document.getElementById('confidence').textContent = `${confidence}/10`;
    if (nbChevaux > 0) {
        document.getElementById('nbChevaux').textContent = nbChevaux;
    }
}

function displayTop5(chevaux) {
    const container = document.getElementById('top5');
    container.innerHTML = '';
    
    if (!chevaux || chevaux.length === 0) {
        container.innerHTML = '<p class="text-gray-400 col-span-full text-center">Aucun cheval disponible</p>';
        return;
    }
    
    chevaux.slice(0, 5).forEach((cheval, index) => {
        const colors = ['bg-yellow-600', 'bg-gray-400', 'bg-orange-600', 'bg-blue-600', 'bg-purple-600'];
        const color = colors[index] || 'bg-gray-600';
        
        // Déterminer si c'est un value bet (cote élevée avec bon score)
        const isValueBet = (cheval.cote || 0) > 10 && (cheval.score || 0) > 40;
        
        const card = document.createElement('div');
        card.className = `${color} rounded-xl p-6 text-center card-hover cursor-pointer transform transition`;
        card.innerHTML = `
            <div class="text-5xl font-bold mb-2">#${cheval.numero || '?'}</div>
            <div class="font-bold text-lg mb-2">${cheval.nom || 'Inconnu'}</div>
            <div class="text-sm opacity-90 mb-3">Cote: ${cheval.cote || 'N/A'}</div>
            <div class="bg-white/20 rounded-lg py-2 mb-2">
                <div class="text-2xl font-bold">${cheval.score || 0}</div>
                <div class="text-xs">Score</div>
            </div>
            <div class="text-xs opacity-75">${cheval.profil || ''}</div>
            ${isValueBet ? '<div class="mt-2 text-yellow-300">💎 Value Bet</div>' : ''}
        `;
        
        // Click pour détails
        card.addEventListener('click', () => showHorseDetails(cheval));
        
        container.appendChild(card);
    });
}

function displayParis(paris, budget) {
    console.log('🔍 displayParis appelé avec:', { paris, budget });
    
    const container = document.getElementById('paris');
    if (!container) {
        console.error('❌ Container paris introuvable');
        return;
    }
    
    container.innerHTML = '';
    
    // Vérification stricte
    if (!paris || !Array.isArray(paris) || paris.length === 0) {
        console.log('⚠️ Aucun pari à afficher');
        container.innerHTML = '<p class="text-gray-400 text-center py-4">Aucun pari recommandé</p>';
        const totalBudgetEl = document.getElementById('totalBudget');
        if (totalBudgetEl) totalBudgetEl.textContent = '0€';
        return;
    }
    
    let totalMise = 0;
    
    paris.forEach((pari, index) => {
        try {
            console.log(`🎲 Traitement pari ${index}:`, pari);
            
            // Sécurité maximale
            if (!pari || typeof pari !== 'object') {
                console.warn(`⚠️ Pari ${index} invalide, ignoré`);
                return;
            }
            
            totalMise += (pari.mise || 0);
            
            // CORRECTION : Utiliser chevaux au lieu de numeros
            let chevauxText = 'N/A';
            let chevauxNomsText = '';
            
            try {
                // Le backend envoie "chevaux" (numéros) et "chevaux_noms" (noms)
                if (pari.chevaux && Array.isArray(pari.chevaux) && pari.chevaux.length > 0) {
                    chevauxText = pari.chevaux.join(' - ');
                } else if (pari.chevaux) {
                    chevauxText = String(pari.chevaux);
                }
                
                // Ajouter les noms si disponibles
                if (pari.chevaux_noms && Array.isArray(pari.chevaux_noms) && pari.chevaux_noms.length > 0) {
                    chevauxNomsText = `<div class="text-xs text-gray-400 mt-1">${pari.chevaux_noms.join(', ')}</div>`;
                }
            } catch (e) {
                console.error(`❌ Erreur traitement chevaux pari ${index}:`, e);
                chevauxText = 'Erreur';
            }
            
            console.log(`✅ Pari ${index} - Chevaux: ${chevauxText}`);
            
            const card = document.createElement('div');
            card.className = 'bg-gray-700 rounded-xl p-5 flex items-center justify-between card-hover';
            card.innerHTML = `
                <div class="flex-1">
                    <div class="flex items-center gap-3 mb-2">
                        <span class="text-2xl">${getParisEmoji(pari.type || 'UNKNOWN')}</span>
                        <div class="font-bold text-lg">${pari.type || 'Pari'}</div>
                    </div>
                    <div class="text-sm text-gray-300 space-y-1">
                        <div>📍 Chevaux: <span class="font-mono font-bold text-blue-400">${chevauxText}</span></div>
                        ${chevauxNomsText}
                        <div>📊 ROI espéré: <span class="font-bold text-green-400">${pari.roi_attendu || pari.roi_estime || 0}x</span></div>
                        ${pari.justification ? `<div class="text-gray-400 italic mt-2">"${pari.justification}"</div>` : ''}
                    </div>
                </div>
                <div class="text-right ml-4">
                    <div class="text-3xl font-bold text-green-400">${pari.mise || 0}€</div>
                    <div class="text-xs text-gray-400 mt-1">Mise</div>
                </div>
            `;
            
            container.appendChild(card);
        } catch (error) {
            console.error(`❌ Erreur affichage pari ${index}:`, error);
        }
    });
    
    const totalBudgetEl = document.getElementById('totalBudget');
    if (totalBudgetEl) {
        totalBudgetEl.textContent = `${totalMise}€ / ${budget}€`;
    }
    
    console.log('✅ displayParis terminé avec succès');
}

function displayValueBets(valueBets) {
    console.log('🔍 displayValueBets appelé avec:', valueBets);
    
    const section = document.getElementById('valueBetsSection');
    if (!section) {
        console.error('❌ Section valueBets introuvable');
        return;
    }
    
    if (!valueBets || !Array.isArray(valueBets) || valueBets.length === 0) {
        console.log('⚠️ Aucun value bet à afficher');
        section.classList.add('hidden');
        return;
    }
    
    const container = document.getElementById('valueBets');
    if (!container) {
        console.error('❌ Container valueBets introuvable');
        return;
    }
    
    container.innerHTML = '';
    
    valueBets.forEach((vb, index) => {
        try {
            if (!vb || typeof vb !== 'object') {
                console.warn(`⚠️ Value bet ${index} invalide, ignoré`);
                return;
            }
            
            const card = document.createElement('div');
            card.className = 'bg-gradient-to-r from-yellow-900/50 to-orange-900/50 border border-yellow-500/30 rounded-xl p-5';
            card.innerHTML = `
                <div class="flex items-center justify-between">
                    <div class="flex-1">
                        <div class="flex items-center gap-3 mb-2">
                            <span class="text-3xl">💎</span>
                            <div class="font-bold text-xl">#${vb.numero || '?'} - ${vb.nom || 'Inconnu'}</div>
                        </div>
                        <div class="text-sm text-gray-300">
                            <div>Edge: <span class="font-bold text-green-400">+${vb.edge || 0}%</span></div>
                            <div class="mt-1 text-gray-400">${vb.raison || 'N/A'}</div>
                        </div>
                    </div>
                    <div class="text-right">
                        <div class="text-2xl font-bold text-yellow-400">${vb.cote || 'N/A'}</div>
                        <div class="text-xs text-gray-400">Cote</div>
                    </div>
                </div>
            `;
            
            container.appendChild(card);
        } catch (error) {
            console.error(`❌ Erreur affichage value bet ${index}:`, error);
        }
    });
    
    section.classList.remove('hidden');
    console.log('✅ displayValueBets terminé');
}

function displayRaisonnement(text) {
    const container = document.getElementById('raisonnement');
    
    if (!text || text === 'Aucune analyse disponible') {
        container.innerHTML = '<p class="text-gray-400 italic">Aucune analyse disponible</p>';
        return;
    }
    
    // Affichage amélioré avec formatage
    container.innerHTML = `
        <div class="space-y-4">
            <div class="flex items-center gap-3 mb-4">
                <span class="text-3xl">🤖</span>
                <h4 class="text-xl font-bold text-blue-300">Analyse Gemini</h4>
            </div>
            <div class="bg-gray-800/50 rounded-lg p-6 border border-blue-500/20">
                <div class="prose prose-invert max-w-none">
                    ${text.split('\n\n').map(paragraph => {
                        if (!paragraph.trim()) return '';
                        
                        // Détecter titres
                        if (paragraph.startsWith('###') || paragraph.startsWith('**')) {
                            const title = paragraph.replace(/^###\s*/, '').replace(/\*\*/g, '');
                            return `<h5 class="text-lg font-bold text-blue-300 mt-3 mb-2">${title}</h5>`;
                        }
                        
                        // Détecter listes
                        if (paragraph.includes('\n-') || paragraph.includes('\n•')) {
                            const items = paragraph.split('\n').filter(l => l.trim());
                            const listItems = items.map(item => {
                                if (item.trim().startsWith('-') || item.trim().startsWith('•')) {
                                    return `<li class="ml-4">${item.replace(/^[-•]\s*/, '')}</li>`;
                                }
                                return `<p class="text-gray-200">${item}</p>`;
                            }).join('');
                            return `<ul class="list-disc list-inside space-y-1">${listItems}</ul>`;
                        }
                        
                        // Paragraphe normal
                        return `<p class="text-gray-200 leading-relaxed">${paragraph.replace(/\n/g, '<br>')}</p>`;
                    }).join('')}
                </div>
            </div>
            <button 
                onclick="showDetailedAnalysis()" 
                class="mt-4 px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg transition duration-200 font-semibold"
            >
                📊 Voir l'analyse complète détaillée
            </button>
        </div>
    `;
}

// Nouvelle fonction pour afficher l'analyse IA complète
function showDetailedAnalysis() {
    if (!state.currentAnalysis || !state.currentAnalysis.data) {
        alert('Aucune analyse disponible');
        return;
    }
    
    const data = state.currentAnalysis.data;
    
    // Construction du message détaillé
    let details = `
🤖 ANALYSE COMPLÈTE GEMINI AI
═══════════════════════════════════════

📊 SCÉNARIO DE COURSE
Type: ${data.scenario_course || 'N/A'}
Confiance: ${data.confiance_globale || 0}/10

🎯 TOP 5 ANALYSE
${(data.top_5_chevaux || []).map((c, i) => `
${i + 1}. #${c.numero} ${c.nom}
   Score: ${c.score}/100
   Cote: ${c.cote}
   Profil: ${c.profil}
   
   💪 Points forts:
   ${c.points_forts}
   
   ⚠️ Points faibles:
   ${c.points_faibles}
`).join('\n')}

💎 VALUE BETS DÉTECTÉS
${(data.value_bets_detectes || []).map(v => `
• #${v.numero} ${v.nom}
  Cote: ${v.cote} | Edge: ${v.edge}%
  Raison: ${v.raison}
`).join('\n')}

💰 PARIS RECOMMANDÉS
Budget total: ${data.budget_total || 0}€
Budget utilisé: ${data.budget_utilise || 0}€
ROI moyen attendu: ${data.roi_moyen_attendu || 0}x

${(data.paris_recommandes || []).map(p => `
📍 ${p.type}
   Chevaux: ${(p.chevaux || []).join('-')} (${(p.chevaux_noms || []).join(', ')})
   Mise: ${p.mise}€
   ROI espéré: ${p.roi_attendu}x
   Justification: ${p.justification}
`).join('\n')}

🧠 ANALYSE TACTIQUE
${data.analyse_tactique || 'Non disponible'}

💬 CONSEIL FINAL
${data.conseil_final || 'Non disponible'}
    `;
    
    // Afficher dans un textarea pour permettre la copie
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4';
    modal.innerHTML = `
        <div class="bg-gray-800 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div class="p-6 border-b border-gray-700 flex justify-between items-center">
                <h3 class="text-2xl font-bold">🤖 Analyse Complète IA</h3>
                <button onclick="this.closest('.fixed').remove()" class="text-3xl hover:text-red-500">×</button>
            </div>
            <div class="p-6 overflow-y-auto flex-1">
                <textarea 
                    readonly 
                    class="w-full h-full bg-gray-900 text-gray-200 p-4 rounded-lg font-mono text-sm resize-none"
                    style="min-height: 500px;"
                >${details}</textarea>
            </div>
            <div class="p-6 border-t border-gray-700">
                <button 
                    onclick="navigator.clipboard.writeText(this.previousElementSibling.querySelector('textarea').value); alert('Copié !');"
                    class="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg transition duration-200 font-semibold mr-3"
                >
                    📋 Copier l'analyse
                </button>
                <button 
                    onclick="this.closest('.fixed').remove()"
                    class="px-6 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition duration-200 font-semibold"
                >
                    Fermer
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

// ============================================================================
// DÉTAILS CHEVAL (MODAL)
// ============================================================================

function showHorseDetails(cheval) {
    const details = `
📊 Détails #${cheval.numero} - ${cheval.nom}

🏆 Analyse:
- Score: ${cheval.score || 0}/100
- Rang: ${cheval.rang || 'N/A'}
- Profil: ${cheval.profil || 'N/A'}
- Cote: ${cheval.cote || 'N/A'}

💪 Points forts:
${cheval.points_forts || 'Non disponible'}

⚠️ Points faibles:
${cheval.points_faibles || 'Non disponible'}

${(cheval.cote > 10 && cheval.score > 40) ? '\n💎 VALUE BET potentiel !' : ''}
    `;
    
    alert(details);
}

// ============================================================================
// DÉBRIEFING
// ============================================================================

async function handleDebriefing() {
    if (!state.currentAnalysis) {
        showError('Aucune analyse en cours');
        return;
    }
    
    const { date, reunion, course } = state.currentAnalysis;
    
    showLoading();
    
    try {
        const url = `${CONFIG.API_URL}/debrief?date=${date}&r=${reunion}&c=${course}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`Erreur ${response.status}`);
        }
        
        const data = await response.json();
        displayDebriefing(data);
        
    } catch (error) {
        showError('Débriefing non disponible (course pas encore terminée ?)');
    } finally {
        hideLoading();
    }
}

function displayDebriefing(data) {
    try {
        // Arrivée réelle
        const arrivee = (data.arrivee && Array.isArray(data.arrivee)) 
            ? data.arrivee.join(' - ') 
            : 'N/A';
        
        // Non-partants
        const nonPartants = (data.non_partants && Array.isArray(data.non_partants) && data.non_partants.length > 0)
            ? `\n🚫 Non-partants: ${data.non_partants.join(', ')}`
            : '';
        
        // Paris gagnants détaillés
        let parisDetails = '';
        if (data.paris_joues && Array.isArray(data.paris_joues)) {
            parisDetails = '\n📋 Détail des paris:\n';
            data.paris_joues.forEach((pari, index) => {
                const status = pari.gagnant ? '✅' : '❌';
                const gainInfo = pari.gagnant ? ` → Gain: ${pari.gain}€ (ROI: ${pari.roi}x)` : '';
                parisDetails += `${status} ${pari.type} (${pari.chevaux.join('-')}) - Mise: ${pari.mise}€${gainInfo}\n`;
            });
        }
        
        // Message final
        const message = `
🏁 DÉBRIEFING DE COURSE

📅 ${data.date} - R${data.reunion}C${data.course}
🏟️ ${data.hippodrome || 'N/A'}

🏆 ARRIVÉE RÉELLE
${arrivee}${nonPartants}

💰 PERFORMANCES
ROI Réel: ${data.roi_reel || 0}x
Gains: ${data.gains_total || 0}€
Mises: ${data.mise_totale || 0}€

🎯 PRÉCISION
Top-3: ${data.precision_top_3 || 0}%
Top-5 prédit: ${(data.top_5_predit || []).join(', ')}
Top-5 réel: ${(data.top_5_reel || []).join(', ')}

${parisDetails}

💬 COMMENTAIRE
${data.commentaire || 'N/A'}
        `;
        
        // Afficher dans une modale plus élaborée si possible
        alert(message);
        
        // Optionnel: Ajouter une section dédiée dans le HTML
        const debriefSection = document.getElementById('debriefSection');
        if (debriefSection) {
            debriefSection.classList.remove('hidden');
            const debriefContent = document.getElementById('debriefContent');
            if (debriefContent) {
                debriefContent.innerHTML = `
                    <div class="bg-gray-700 rounded-xl p-6 space-y-4">
                        <div class="text-center">
                            <h3 class="text-2xl font-bold mb-2">🏁 Arrivée: ${arrivee}</h3>
                            <p class="text-lg text-green-400">ROI Réel: ${data.roi_reel}x</p>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div class="bg-gray-800 p-4 rounded-lg">
                                <div class="text-sm text-gray-400">Gains Total</div>
                                <div class="text-xl font-bold text-green-400">${data.gains_total}€</div>
                            </div>
                            <div class="bg-gray-800 p-4 rounded-lg">
                                <div class="text-sm text-gray-400">Précision Top-3</div>
                                <div class="text-xl font-bold text-blue-400">${data.precision_top_3}%</div>
                            </div>
                        </div>
                        <div class="bg-gray-800 p-4 rounded-lg">
                            <h4 class="font-bold mb-2">📋 Détail des paris</h4>
                            ${data.paris_joues ? data.paris_joues.map(p => `
                                <div class="flex justify-between items-center py-2 border-b border-gray-700">
                                    <span>${p.gagnant ? '✅' : '❌'} ${p.type} (${p.chevaux.join('-')})</span>
                                    <span class="${p.gagnant ? 'text-green-400' : 'text-red-400'}">${p.gagnant ? '+' + p.gain : '-' + p.mise}€</span>
                                </div>
                            `).join('') : 'Aucun pari'}
                        </div>
                        <div class="bg-blue-900/30 p-4 rounded-lg border border-blue-500/30">
                            <p class="text-sm">${data.commentaire}</p>
                        </div>
                    </div>
                `;
            }
        }
        
    } catch (error) {
        console.error('❌ Erreur displayDebriefing:', error);
        alert('Erreur lors de l\'affichage du débriefing: ' + error.message);
    }
}

// ============================================================================
// HISTORIQUE
// ============================================================================

async function loadHistory() {
    try {
        // Charger depuis le serveur d'abord
        const response = await fetch(`${CONFIG.API_URL}/history`);
        if (response.ok) {
            const data = await response.json();
            state.history = data.history || [];
            console.log(`✅ Historique chargé depuis serveur: ${state.history.length} entrées`);
        } else {
            // Fallback localStorage si serveur indisponible
            const stored = localStorage.getItem(CONFIG.STORAGE_KEY);
            state.history = stored ? JSON.parse(stored) : [];
            console.log(`⚠️ Historique chargé depuis localStorage (serveur indisponible)`);
        }
        displayHistory();
    } catch (error) {
        console.error('❌ Erreur chargement historique:', error);
        // Fallback localStorage
        const stored = localStorage.getItem(CONFIG.STORAGE_KEY);
        state.history = stored ? JSON.parse(stored) : [];
        displayHistory();
    }
}

function saveToHistory(formData, data) {
    try {
        console.log('💾 saveToHistory appelée', { formData, data });
        
        // Créer l'entrée d'historique
        const entry = {
            date: formData.date,
            reunion: formData.reunion,
            course: formData.course,
            hippodrome: data.hippodrome || 'N/A',
            scenario: data.scenario_course || 'N/A',
            budget: formData.budget,
            roi_attendu: data.roi_moyen_attendu || 0,
            nb_paris: (data.paris_recommandes || []).length,
            timestamp: new Date().toISOString()
        };
        
        console.log('📝 Entrée créée:', entry);
        
        // Ajouter au début de l'historique
        state.history.unshift(entry);
        
        // Limiter à 50 entrées
        state.history = state.history.slice(0, CONFIG.MAX_HISTORY);
        
        console.log(`📊 Historique: ${state.history.length} entrées`);
        
        // Sauvegarder dans localStorage (backup)
        try {
            localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(state.history));
            console.log('✅ Historique sauvegardé dans localStorage');
        } catch (e) {
            console.warn('⚠️ Erreur sauvegarde localStorage:', e);
        }
        
        // Afficher l'historique
        displayHistory();
        
        console.log('✅ saveToHistory terminée');
        
    } catch (error) {
        console.error('❌ Erreur saveToHistory:', error);
    }
}

function displayHistory() {
    if (state.history.length === 0) {
        return;
    }
    
    const container = document.getElementById('history');
    const section = document.getElementById('historySection');
    
    container.innerHTML = state.history.map(item => `
        <div class="bg-gray-700 rounded-lg p-4 flex items-center justify-between hover:bg-gray-600 transition cursor-pointer"
             onclick="reloadAnalysis('${item.date}', ${item.reunion}, ${item.course})">
            <div>
                <div class="font-bold">${item.date} - R${item.reunion}C${item.course}</div>
                <div class="text-sm text-gray-400">
                    ${item.scenario || item.hippodrome || 'N/A'} 
                    ${item.confidence ? `- ${item.confidence}/10` : ''}
                    ${item.roi_attendu ? `- ROI ${item.roi_attendu}x` : ''}
                </div>
            </div>
            <div class="text-gray-400">→</div>
        </div>
    `).join('');
    
    section.classList.remove('hidden');
}

function reloadAnalysis(date, reunion, course) {
    document.getElementById('date').value = date;
    document.getElementById('reunion').value = reunion;
    document.getElementById('course').value = course;
    scrollToTop();
}

// ============================================================================
// STATUS API
// ============================================================================

async function checkAPIStatus() {
    try {
        const response = await fetch(`${CONFIG.API_URL}/health`, { timeout: 5000 });
        const data = await response.json();
        
        const statusDiv = document.getElementById('apiStatus');
        if (data.status === 'healthy') {
            statusDiv.innerHTML = '🟢 En ligne';
            statusDiv.className = 'font-bold text-green-400';
        } else {
            statusDiv.innerHTML = '🟡 Dégradé';
            statusDiv.className = 'font-bold text-yellow-400';
        }
    } catch (error) {
        const statusDiv = document.getElementById('apiStatus');
        statusDiv.innerHTML = '🔴 Hors ligne';
        statusDiv.className = 'font-bold text-red-400';
    }
}

// ============================================================================
// UTILITAIRES
// ============================================================================

function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

function showError(message) {
    document.getElementById('errorMessage').textContent = message;
    document.getElementById('error').classList.remove('hidden');
    scrollToTop();
}

function hideError() {
    document.getElementById('error').classList.add('hidden');
}

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function getParisEmoji(type) {
    const emojis = {
        'SIMPLE_GAGNANT': '🎯',
        'SIMPLE_PLACE': '📍',
        'COUPLE_GAGNANT': '🤝',
        'COUPLE_PLACE': '👥',
        'TRIO': '🎲',
        'DEUX_SUR_QUATRE': '🔢',
        'MULTI': '🎰'
    };
    return emojis[type] || '💰';
}

// ============================================================================
// SAUVEGARDE LOCALE
// ============================================================================

function saveToLocalStorage(formData, data) {
    try {
        let history = JSON.parse(localStorage.getItem(CONFIG.STORAGE_KEY) || '[]');
        
        history.unshift({
            date: formData.date,
            reunion: formData.reunion,
            course: formData.course,
            scenario: data.scenario_course || 'N/A',
            budget: formData.budget,
            roi: data.roi_moyen_attendu || 0,
            nb_paris: (data.paris_recommandes || []).length,
            timestamp: new Date().toISOString()
        });
        
        // Garder max 50 entrées
        history = history.slice(0, 50);
        
        localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(history));
        
        console.log('✅ Analyse sauvegardée dans localStorage');
        
        // Rafraîchir l'affichage historique
        displayHistory();
        
    } catch (e) {
        console.error('❌ Erreur sauvegarde localStorage:', e);
    }
}

// ============================================================================
// ANALYSE COMPLÈTE (MODALE)
// ============================================================================

function showFullAnalysis() {
    if (!state.currentAnalysis || !state.currentAnalysis.data) {
        alert('❌ Aucune analyse disponible\n\nVeuillez d\'abord analyser une course');
        return;
    }
    
    const data = state.currentAnalysis.data;
    
    // Créer modale
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black/90 flex items-center justify-center z-50 p-4';
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
    
    modal.innerHTML = `
        <div class="bg-gray-900 rounded-2xl max-w-5xl w-full max-h-[90vh] flex flex-col border-2 border-blue-500/30">
            <!-- Header -->
            <div class="p-6 border-b border-gray-700 flex justify-between items-center bg-gradient-to-r from-blue-900/50 to-purple-900/50">
                <h2 class="text-3xl font-bold flex items-center gap-3">
                    <span>🤖</span>
                    <span>Analyse Complète Gemini</span>
                </h2>
                <button onclick="this.closest('.fixed').remove()" class="text-4xl hover:text-red-500 transition">×</button>
            </div>
            
            <!-- Content -->
            <div class="p-6 overflow-y-auto flex-1">
                <div class="space-y-6">
                    <!-- Scénario -->
                    <div class="bg-gradient-to-r from-yellow-900/30 to-orange-900/30 border border-yellow-500/30 rounded-xl p-6">
                        <h3 class="text-2xl font-bold mb-3">📊 Scénario de Course</h3>
                        <div class="text-xl font-bold text-yellow-300">${data.scenario_course || 'N/A'}</div>
                        <div class="text-gray-300 mt-2">Confiance IA: <span class="text-green-400 font-bold">${data.confiance_globale || 0}/10</span></div>
                        ${data.conseil_final ? `
                            <div class="mt-4 p-4 bg-blue-900/30 rounded-lg border border-blue-500/30">
                                <div class="font-bold text-blue-300 mb-2">💡 Conseil Final</div>
                                <div class="text-gray-200">${data.conseil_final}</div>
                            </div>
                        ` : ''}
                    </div>
                    
                    <!-- Top 5 -->
                    <div class="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
                        <h3 class="text-2xl font-bold mb-4">🏆 Top 5 Analysé par IA</h3>
                        ${(data.top_5_chevaux || []).map((c, i) => {
                            const colors = [
                                'border-yellow-500 bg-yellow-900/20',
                                'border-gray-400 bg-gray-800/20',
                                'border-orange-600 bg-orange-900/20',
                                'border-blue-500 bg-blue-900/20',
                                'border-purple-500 bg-purple-900/20'
                            ];
                            return `
                                <div class="mb-4 p-4 rounded-lg border-l-4 ${colors[i]}">
                                    <div class="flex justify-between items-start mb-3">
                                        <div>
                                            <span class="text-3xl font-bold">${i + 1}.</span>
                                            <span class="text-2xl font-bold ml-2">#${c.numero} ${c.nom || ''}</span>
                                        </div>
                                        <div class="text-right">
                                            <div class="text-2xl font-bold text-yellow-400">${c.score || 0}/100</div>
                                            <div class="text-sm text-gray-400">Cote: ${c.cote || 'N/A'}</div>
                                        </div>
                                    </div>
                                    <div class="text-sm space-y-2">
                                        <div><span class="text-blue-300 font-semibold">Profil:</span> <span class="text-gray-300">${c.profil || 'N/A'}</span></div>
                                        <div><span class="text-green-300 font-semibold">💪 Points forts:</span> <div class="text-gray-300 mt-1">${c.points_forts || 'N/A'}</div></div>
                                        <div><span class="text-red-300 font-semibold">⚠️ Points faibles:</span> <div class="text-gray-300 mt-1">${c.points_faibles || 'N/A'}</div></div>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                    
                    <!-- Value Bets -->
                    ${(data.value_bets_detectes || []).length > 0 ? `
                        <div class="bg-gradient-to-r from-yellow-900/30 to-orange-900/30 border border-yellow-500/30 rounded-xl p-6">
                            <h3 class="text-2xl font-bold mb-4">💎 Value Bets Détectés</h3>
                            ${(data.value_bets_detectes || []).map(vb => `
                                <div class="mb-3 p-4 bg-gray-800/50 rounded-lg border border-yellow-500/20">
                                    <div class="flex justify-between items-start">
                                        <div>
                                            <div class="text-xl font-bold">#${vb.numero || '?'} ${vb.nom || ''}</div>
                                            <div class="text-sm text-gray-400 mt-1 italic">"${vb.raison || 'N/A'}"</div>
                                        </div>
                                        <div class="text-right">
                                            <div class="text-2xl font-bold text-yellow-400">${vb.cote || 'N/A'}</div>
                                            <div class="text-sm text-green-400">Edge: +${vb.edge || 0}%</div>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                    
                    <!-- Paris -->
                    <div class="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
                        <h3 class="text-2xl font-bold mb-4">💰 Paris Recommandés (${(data.paris_recommandes || []).length})</h3>
                        <div class="mb-6 p-4 bg-gradient-to-r from-green-900/30 to-blue-900/30 rounded-lg flex justify-between">
                            <div>
                                <div class="text-sm text-gray-400">Budget Utilisé</div>
                                <div class="text-2xl font-bold text-green-400">${data.budget_utilise || 0}€</div>
                            </div>
                            <div>
                                <div class="text-sm text-gray-400">Budget Total</div>
                                <div class="text-2xl font-bold text-gray-300">${data.budget_total || 0}€</div>
                            </div>
                            <div>
                                <div class="text-sm text-gray-400">ROI Moyen Attendu</div>
                                <div class="text-2xl font-bold text-yellow-400">${data.roi_moyen_attendu || 0}x</div>
                            </div>
                        </div>
                        ${(data.paris_recommandes || []).map((p, i) => `
                            <div class="mb-4 p-5 bg-gray-700/50 rounded-lg border border-gray-600 hover:border-blue-500/50 transition">
                                <div class="flex justify-between items-start mb-3">
                                    <div class="flex-1">
                                        <div class="flex items-center gap-2 mb-2">
                                            <span class="text-xl">${getParisEmoji(p.type || '')}</span>
                                            <span class="text-lg font-bold">${p.type || 'N/A'}</span>
                                        </div>
                                        <div class="text-sm space-y-1">
                                            <div><span class="text-gray-400">Chevaux:</span> <span class="font-mono font-bold text-blue-400">${(p.chevaux || []).join('-')}</span></div>
                                            <div class="text-gray-400">${(p.chevaux_noms || []).join(', ')}</div>
                                        </div>
                                    </div>
                                    <div class="text-right ml-4">
                                        <div class="text-3xl font-bold text-green-400">${p.mise || 0}€</div>
                                        <div class="text-sm text-yellow-400">ROI: ${p.roi_attendu || 0}x</div>
                                    </div>
                                </div>
                                <div class="mt-3 p-3 bg-gray-800/50 rounded text-sm text-gray-300 italic">
                                    "${p.justification || 'N/A'}"
                                </div>
                            </div>
                        `).join('')}
                    </div>
                    
                    <!-- Analyse tactique -->
                    <div class="bg-gradient-to-r from-blue-900/30 to-purple-900/30 border border-blue-500/30 rounded-xl p-6">
                        <h3 class="text-2xl font-bold mb-4">🧠 Analyse Tactique Complète</h3>
                        <div class="text-gray-200 whitespace-pre-line leading-relaxed">${data.analyse_tactique || 'Non disponible'}</div>
                    </div>
                </div>
            </div>
            
            <!-- Footer -->
            <div class="p-6 border-t border-gray-700 flex gap-3 bg-gray-800/50">
                <button 
                    onclick="
                        const text = JSON.stringify(${JSON.stringify(data).replace(/"/g, '&quot;')}, null, 2);
                        navigator.clipboard.writeText(text).then(() => {
                            alert('✅ Analyse copiée dans le presse-papier!');
                        }).catch(() => {
                            alert('❌ Erreur copie. Utilisez Ctrl+C manuellement.');
                        });
                    "
                    class="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg transition flex items-center justify-center gap-2"
                >
                    <span>📋</span>
                    <span>Copier JSON</span>
                </button>
                <button 
                    onclick="this.closest('.fixed').remove()"
                    class="flex-1 bg-gray-700 hover:bg-gray-600 text-white font-bold py-3 px-6 rounded-lg transition"
                >
                    Fermer
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

// ============================================================================
// EXPORT
// ============================================================================

console.log('✅ App.js chargé');
