// middleware/auth.js
const axios = require('axios');
const jwt   = require('jsonwebtoken');

// ── Config ───────────────────────────────────────────────────
const CONFIG = {
    GATEWAY_URL: process.env.GATEWAY_URL || 'http://localhost:8083',
    JWT_SECRET:  process.env.JWT_SECRET,
    CACHE_TTL:   10 * 60 * 1000,  // 10 minutes
    TIMEOUT:     5000,
};

// ── Cache mémoire ────────────────────────────────────────────
const _cache = new Map();

function cacheGet(key) {
    const item = _cache.get(key);
    if (!item) return null;
    if (Date.now() > item.exp) { _cache.delete(key); return null; }
    return item.data;
}

function cacheSet(key, data) {
    _cache.set(key, { data, exp: Date.now() + CONFIG.CACHE_TTL });
}

// ── Fetch user via Gateway → Django /auth/all_users/<id>/ ────
async function fetchUserFromDjango(userId, token) {
    try {
        // Gateway route: /auth/** → Django http://localhost:8010
        // Django url: auth/all_users/<user_id>/  → api_get_user_by_id
        const url = `${CONFIG.GATEWAY_URL}/auth/all_users/${userId}/`;
        console.log(`🌐 Appel via Gateway: ${url}`);

        const res = await axios.get(url, {
            headers: { Authorization: `Bearer ${token}` },
            timeout: CONFIG.TIMEOUT
        });

        console.log(`✅ /auth/all_users/${userId}/ →`, {
            role:  res.data?.role,
            email: res.data?.email
        });
        return res.data;

    } catch (err) {
        const status = err.response?.status;
        const detail = err.response?.data?.detail || err.message;
        console.log(`❌ /auth/all_users/${userId}/ échoué: ${status} — ${detail}`);
        return null;
    }
}

// ── Vérification JWT locale (même SECRET_KEY que Django) ─────
function verifyLocal(token) {
    if (!CONFIG.JWT_SECRET) {
        console.error('❌ JWT_SECRET non défini dans config.env !');
        return null;
    }
    try {
        const payload = jwt.verify(token, CONFIG.JWT_SECRET, { algorithms: ['HS256'] });

        if (payload.token_type !== 'access') {
            console.log('❌ Token de type:', payload.token_type, '— access token requis');
            return null;
        }

        console.log(`✅ JWT valide — user_id: ${payload.user_id}`);
        return payload;

    } catch (err) {
        console.log(`❌ JWT invalide: ${err.message}`);
        return null;
    }
}

// ── Résolution principale ─────────────────────────────────────
async function resolveUser(token) {

    // 1. Vérification locale JWT
    const payload = verifyLocal(token);
    if (!payload) return null;

    const userId   = payload.user_id.toString();
    const cacheKey = `user:${userId}`;

    // 2. Cache hit
    const cached = cacheGet(cacheKey);
    if (cached) {
        console.log(`📦 Cache hit — user ${userId}`);
        return cached;
    }

    // 3. Appel Django via Gateway
    const data = await fetchUserFromDjango(userId, token);
    if (!data) return null;

    const user = {
        id:          userId,
        role:        data?.role || (data?.is_staff ? 'admin' : 'user'),
        username:    data?.username || data?.email || `user_${userId}`,
        nom_complet: data?.nom_complet || null,
        email:       data?.email || null,
        is_staff:    data?.is_staff || false,
    };

    console.log(`✅ User résolu:`, { id: user.id, role: user.role, nom: user.nom_complet });

    cacheSet(cacheKey, user);
    return user;
}

// ── authMiddleware ────────────────────────────────────────────
const authMiddleware = async (req, res, next) => {
    console.log('\n🔐 ===== AUTH =====');
    try {
        const authHeader = req.headers.authorization || '';
        const token = authHeader.replace('Bearer ', '').trim();

        if (!token) {
            return res.status(401).json({
                success: false,
                message: 'Token manquant',
                code:    'NO_TOKEN'
            });
        }

        const user = await resolveUser(token);

        if (!user) {
            return res.status(401).json({
                success: false,
                message: 'Token invalide ou expiré',
                code:    'INVALID_TOKEN'
            });
        }

        req.user = user;
        next();

    } catch (err) {
        console.error('❌ Auth middleware error:', err.message);
        res.status(500).json({
            success: false,
            message: 'Erreur authentification',
            code:    'AUTH_ERROR'
        });
    }
};

// ── checkRole ─────────────────────────────────────────────────
const checkRole = (...allowedRoles) => (req, res, next) => {
    if (!req.user) {
        return res.status(401).json({
            success: false,
            message: 'Non authentifié',
            code:    'NOT_AUTHENTICATED'
        });
    }

    const roles = allowedRoles.flat(); // supporte checkRole('admin') et checkRole(['admin','manager'])

    if (!roles.includes(req.user.role)) {
        console.log(`❌ Rôle "${req.user.role}" refusé — requis: [${roles.join(', ')}]`);
        return res.status(403).json({
            success: false,
            message: 'Accès refusé — privilèges insuffisants',
            code:    'INSUFFICIENT_PRIVILEGES',
            details: { required: roles, your_role: req.user.role }
        });
    }

    console.log(`✅ Rôle "${req.user.role}" autorisé`);
    next();
};

// ── Invalider cache (ex: après mise à jour utilisateur) ───────
const invalidateUser = (userId) => {
    _cache.delete(`user:${userId}`);
    console.log(`🗑️  Cache invalidé pour user ${userId}`);
};

module.exports = { authMiddleware, checkRole, invalidateUser };
