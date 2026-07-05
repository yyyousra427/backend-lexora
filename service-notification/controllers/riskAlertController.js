// controllers/riskAlertController.js
/**
 * API alertes risque retard — Service Notification
 *
 * Routes exposées :
 *   POST /notifications/risk-alerts/           ← appelé par CLM après analyse
 *   GET  /notifications/risk-alerts/           ← liste filtrée (contrat_id, type, severite)
 *   GET  /notifications/risk-alerts/:id        ← détail d'une alerte
 *   PATCH /notifications/risk-alerts/:id       ← changer statut (resolu, ignore…)
 *   GET  /notifications/risk-alerts/summary/:contrat_id  ← résumé + escalade par contrat
 */

const RiskAlert = require('../models/RiskAlert');

// Logique d'escalade (miroir de get_niveau_escalade Python)
function getNiveauEscalade(occurrenceCount) {
    if (occurrenceCount === 1) {
        return {
            niveau:    'warning',
            label:     'Avertissement / تنبيه',
            escalader: false,
            notifier:  'chef_departement',
        };
    } else if (occurrenceCount === 2) {
        return {
            niveau:    'alert',
            label:     'Alerte / إنذار',
            escalader: false,
            notifier:  'directeur_direction',
        };
    } else {
        return {
            niveau:    'escalade',
            label:     `Escalade (occurrence #${occurrenceCount}) / تصعيد`,
            escalader: true,
            notifier:  'directeur_activite',
        };
    }
}


// ══════════════════════════════════════════════════════════════
// POST /notifications/risk-alerts/
// Réception d'une alerte depuis le service CLM
// ══════════════════════════════════════════════════════════════
exports.createRiskAlert = async (req, res) => {
    try {
        const {
            contrat_id,
            code,
            type        = 'retard',
            description,
            severite,
            article_ref = '',
            suggestion  = '',
        } = req.body;

        // Validation minimale
        if (!contrat_id || !code || !description) {
            return res.status(400).json({
                error: 'contrat_id, code et description sont requis',
            });
        }

        // Compter les occurrences précédentes pour l'escalade
        const previousCount = await RiskAlert.countOccurrences(contrat_id, code);
        const occurrenceCount = previousCount + 1;
        const escalade = getNiveauEscalade(occurrenceCount);

        // Créer l'alerte
        const alert = new RiskAlert({
            contrat_id,
            code,
            type,
            description,
            severite,
            article_ref,
            suggestion,
            created_by_id:   req.user?.id   || null,
            created_by_name: req.user?.nom_complet || req.user?.username || null,
        });

        await alert.save();

        // Log escalade si nécessaire
        if (escalade.escalader) {
            console.warn(
                `[ESCALADE] Contrat ${contrat_id} — code ${code} : ` +
                `${occurrenceCount} occurrences → notifier ${escalade.notifier}`
            );
        }

        res.status(201).json({
            alert,
            occurrence_count: occurrenceCount,
            escalade,
        });

    } catch (err) {
        console.error('[riskAlert] createRiskAlert:', err);
        res.status(500).json({ error: err.message });
    }
};


// ══════════════════════════════════════════════════════════════
// GET /notifications/risk-alerts/
// Liste filtrée des alertes
// ══════════════════════════════════════════════════════════════
exports.getRiskAlerts = async (req, res) => {
    try {
        const {
            contrat_id,
            type,
            severite,
            statut,
            page  = 1,
            limit = 50,
        } = req.query;

        const filter = {};
        if (contrat_id) filter.contrat_id = parseInt(contrat_id, 10);
        if (type)       filter.type       = type;
        if (severite)   filter.severite   = severite;
        if (statut)     filter.statut     = statut;

        const total  = await RiskAlert.countDocuments(filter);
        const alerts = await RiskAlert.find(filter)
            .sort({ createdAt: -1 })
            .skip((parseInt(page, 10) - 1) * parseInt(limit, 10))
            .limit(parseInt(limit, 10));

        // Enrichir chaque alerte avec son occurrence_count + escalade
        const enriched = await Promise.all(
            alerts.map(async (a) => {
                const count = await RiskAlert.countOccurrences(a.contrat_id, a.code);
                return {
                    ...a.toObject(),
                    occurrence_count: count,
                    escalade: getNiveauEscalade(count),
                };
            })
        );
console.log('[DEBUG] filter utilisé:', filter);
console.log('[DEBUG] nombre trouvé:', alerts.length, '/ total:', total);
        res.json({
            alerts: enriched,
            total,
            page:  parseInt(page, 10),
            limit: parseInt(limit, 10),
            pages: Math.ceil(total / parseInt(limit, 10)),
        });

    } catch (err) {
        console.error('[riskAlert] getRiskAlerts:', err);
        res.status(500).json({ error: err.message });
    }
};


// ══════════════════════════════════════════════════════════════
// GET /notifications/risk-alerts/summary/:contrat_id
// Résumé complet d'un contrat : alertes actives + niveaux d'escalade
// ══════════════════════════════════════════════════════════════
exports.getRiskAlertSummary = async (req, res) => {
    try {
        const contrat_id = parseInt(req.params.contrat_id, 10);

        if (!contrat_id) {
            return res.status(400).json({ error: 'contrat_id invalide' });
        }

        // Alertes actives (non résolues), triées par sévérité
        const activeAlerts = await RiskAlert.getActiveAlerts(contrat_id);

        // Enrichir avec occurrence_count + escalade
        const enriched = await Promise.all(
            activeAlerts.map(async (a) => {
                const count = await RiskAlert.countOccurrences(a.contrat_id, a.code);
                return {
                    ...a.toObject(),
                    occurrence_count: count,
                    escalade: getNiveauEscalade(count),
                };
            })
        );

        // Stats globales
        const stats = {
            total:      enriched.length,
            critique:   enriched.filter(a => a.severite === 'critique').length,
            eleve:      enriched.filter(a => a.severite === 'eleve').length,
            moyen:      enriched.filter(a => a.severite === 'moyen').length,
            faible:     enriched.filter(a => a.severite === 'faible').length,
            escalades:  enriched.filter(a => a.escalade.escalader).length,
        };

        // Niveau global du contrat
        let niveau_global = 'ok';
        if (stats.escalades > 0)          niveau_global = 'escalade';
        else if (stats.critique > 0)       niveau_global = 'critique';
        else if (stats.eleve > 0)          niveau_global = 'eleve';
        else if (enriched.length > 0)      niveau_global = 'attention';

        res.json({
            contrat_id,
            niveau_global,
            stats,
            alerts: enriched,
        });

    } catch (err) {
        console.error('[riskAlert] getRiskAlertSummary:', err);
        res.status(500).json({ error: err.message });
    }
};


// ══════════════════════════════════════════════════════════════
// GET /notifications/risk-alerts/:id
// Détail d'une alerte
// ══════════════════════════════════════════════════════════════
exports.getRiskAlert = async (req, res) => {
    try {
        const alert = await RiskAlert.findById(req.params.id);
        if (!alert) {
            return res.status(404).json({ error: 'Alerte non trouvée' });
        }
        const count = await RiskAlert.countOccurrences(alert.contrat_id, alert.code);

        res.json({
            ...alert.toObject(),
            occurrence_count: count,
            escalade: getNiveauEscalade(count),
        });
    } catch (err) {
        console.error('[riskAlert] getRiskAlert:', err);
        res.status(500).json({ error: err.message });
    }
};


// ══════════════════════════════════════════════════════════════
// PATCH /notifications/risk-alerts/:id
// Changer le statut d'une alerte (resolu, ignore, en_cours)
// ══════════════════════════════════════════════════════════════
exports.updateRiskAlertStatus = async (req, res) => {
    try {
        const { statut, resolution_note } = req.body;
        const ALLOWED = ['nouveau', 'en_cours', 'resolu', 'ignore'];

        if (!ALLOWED.includes(statut)) {
            return res.status(400).json({
                error: `statut doit être l'un de: ${ALLOWED.join(', ')}`,
            });
        }

        const update = { statut };
        if (resolution_note !== undefined) update.resolution_note = resolution_note;
        if (statut === 'resolu') update.resolved_at = new Date();

        const alert = await RiskAlert.findByIdAndUpdate(
            req.params.id,
            update,
            { new: true }
        );

        if (!alert) {
            return res.status(404).json({ error: 'Alerte non trouvée' });
        }

        res.json({ alert, updated: true });

    } catch (err) {
        console.error('[riskAlert] updateRiskAlertStatus:', err);
        res.status(500).json({ error: err.message });
    }
};