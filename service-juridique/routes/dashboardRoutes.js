
// const express = require('express');
// const router = express.Router();
// const dashboardController = require('../controllers/dashboardController');



// router.get('/counters', dashboardController.getCounters);
// router.get('/directions-par-direction-centrale', dashboardController.getDirectionsParDirectionCentrale);
// router.get('/activites-breakdown', dashboardController.getActivitesBreakdown);

// module.exports = router;




const express = require('express');
const router = express.Router();
const ctrl = require('../controllers/dashboardController');
const { authMiddleware, checkRole } = require('../middleware/auth');
 

router.get('/counters', authMiddleware, ctrl.getCounters);
router.get('/directions-par-direction-centrale', authMiddleware, ctrl.getDirectionsParDirectionCentrale);
router.get('/activites-breakdown', authMiddleware, ctrl.getActivitesBreakdown);
 
module.exports = router;