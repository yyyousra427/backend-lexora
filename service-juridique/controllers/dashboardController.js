// controllers/dashboardController.js
//
// Endpoint(s) d'agrégation pour le Dashboard de cette plateforme.
// Cette plateforme n'a pas de notion de "projets" / "budget" / "régions",
// mais deux hiérarchies organisationnelles :
//
//   1) Juridique / Organigramme :
//      DirectionCentrale -> Direction -> Departement
//
//   2) Activité :
//      Activite -> DirectionActivite -> DepartementActivite
//      Activite -> Division          -> Structure
//
// Adapte les chemins require() ci-dessous si tes modèles sont ailleurs.

const DirectionCentrale     = require('../models/DirectionCentrale');
const Direction             = require('../models/Direction');
const Departement           = require('../models/Departement');
const Activite              = require('../models/Activite');
const DirectionActivite     = require('../models/DirectionActivite');
const DepartementActivite   = require('../models/DepartementActivite');
const Division              = require('../models/Division');
const Structure             = require('../models/Structure');

const send = (res, status, data) => res.status(status).json(data);

// GET /juridique/dashboard/counters
// Retourne le nombre total de chaque entité (KPI cards).
exports.getCounters = async (req, res) => {
  try {
    const [
      directionsCentrales,
      directions,
      departements,
      activites,
      directionsActivite,
      departementsActivite,
      divisions,
      structures,
    ] = await Promise.all([
      DirectionCentrale.countDocuments(),
      Direction.countDocuments({ actif: true }),
      Departement.countDocuments({ actif: true }),
      Activite.countDocuments(),
      DirectionActivite.countDocuments(),
      DepartementActivite.countDocuments(),
      Division.countDocuments(),
      Structure.countDocuments(),
    ]);

    send(res, 200, {
      success: true,
      data: {
        directionsCentrales,
        directions,
        departements,
        activites,
        directionsActivite,
        departementsActivite,
        divisions,
        structures,
      },
    });
  } catch (err) {
    send(res, 500, { success: false, message: err.message });
  }
};

// GET /juridique/dashboard/directions-par-direction-centrale
// Répartition du nombre de Directions par Direction Centrale
// (utile pour un graphique "Top N" côté frontend, optionnel).
exports.getDirectionsParDirectionCentrale = async (req, res) => {
  try {
    const data = await Direction.aggregate([
      { $match: { actif: true } },
      {
        $group: {
          _id: '$directionCentrale',
          count: { $sum: 1 },
        },
      },
      {
        $lookup: {
          from: 'directioncentrales', // adapte le nom de collection si différent
          localField: '_id',
          foreignField: '_id',
          as: 'directionCentrale',
        },
      },
      { $unwind: { path: '$directionCentrale', preserveNullAndEmptyArrays: true } },
      {
        $project: {
          _id: 0,
          directionCentraleId: '$_id',
          nom: '$directionCentrale.nom',
          code: '$directionCentrale.code',
          count: 1,
        },
      },
      { $sort: { count: -1 } },
    ]);

    send(res, 200, { success: true, data });
  } catch (err) {
    send(res, 500, { success: false, message: err.message });
  }
};

// GET /juridique/dashboard/activites-breakdown
// Répartition des sous-entités d'activité (utile pour un donut/bar chart).
exports.getActivitesBreakdown = async (req, res) => {
  try {
    const [directionsActivite, departementsActivite, divisions, structures] = await Promise.all([
      DirectionActivite.countDocuments(),
      DepartementActivite.countDocuments(),
      Division.countDocuments(),
      Structure.countDocuments(),
    ]);

    send(res, 200, {
      success: true,
      data: { directionsActivite, departementsActivite, divisions, structures },
    });
  } catch (err) {
    send(res, 500, { success: false, message: err.message });
  }
};