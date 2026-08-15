const express = require('express');
const router = express.Router();
const ctrl = require('../controllers/activiteController');
const { authMiddleware, checkRole } = require('../middleware/auth');

// Routes publiques (avec authentification seulement)
router.get('/', authMiddleware, ctrl.getAll);
router.get('/:id', authMiddleware, ctrl.getOne);

// Routes réservées aux admins
router.post('/', authMiddleware, checkRole('admin'), ctrl.create);
router.put('/:id', authMiddleware, checkRole('admin'), ctrl.update);
router.delete('/:id', authMiddleware, checkRole('admin'), ctrl.remove);

module.exports = router;