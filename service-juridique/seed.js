// // /**
// //  * seed.js — Peuple Direction + Departement uniquement
// //  * Usage: node seed.js
// //  */
// // const dotenv = require('dotenv');
// // dotenv.config({ path: './config.env' });

// // const mongoose    = require('mongoose');
// // const Direction   = require('./models/Direction');
// // const Departement = require('./models/Departement');

// // const data = [
// //   {
// //     code: 'DC',
// //     nom:  'Direction Contrats',
// //     description: 'Gestion et suivi des contrats',
// //     departements: [
// //       { code: 'DC-CONT', nom: 'Département Contrats',               description: 'Rédaction et suivi des contrats' },
// //       { code: 'DC-AC',   nom: 'Département Assistance et Conseils', description: 'Assistance juridique et conseils' },
// //       { code: 'DC-DL',   nom: 'Département Dépôt Légal',            description: 'Gestion du dépôt légal' },
// //     ],
// //   },
// //   {
// //     code: 'DRD',
// //     nom:  'Direction Règlement des Différends',
// //     description: 'Règlement amiable et judiciaire des différends',
// //     departements: [
// //       { code: 'DRD-CI',   nom: 'Département Contentieux Interne',       description: 'Traitement des contentieux internes' },
// //       { code: 'DRD-CINT', nom: 'Département Contentieux International', description: 'Traitement des contentieux internationaux' },
// //       { code: 'DRD-AL',   nom: 'Département Analyses des Litiges',      description: 'Analyse et suivi des litiges' },
// //     ],
// //   },
// //   {
// //     code: 'DER',
// //     nom:  'Direction Études et Réglementation',
// //     description: 'Veille juridique, études et réglementation',
// //     departements: [
// //       { code: 'DER-AJ',   nom: 'Département Analyses Juridiques',                          description: 'Analyses et avis juridiques' },
// //       { code: 'DER-RVJ',  nom: 'Département Réglementation et Veille Juridique',           description: 'Veille réglementaire' },
// //       { code: 'DER-SJOP', nom: 'Département Suivi Juridique des Opérations Patrimoniales', description: 'Suivi juridique des opérations patrimoniales' },
// //     ],
// //   },
// // ];

// // const run = async () => {
// //   await mongoose.connect(process.env.MONGODB_URI);
// //   console.log('✅ MongoDB connecté\n');

// //   await Direction.deleteMany({});
// //   await Departement.deleteMany({});
// //   console.log('🗑️  Collections nettoyées\n');

// //   for (const item of data) {
// //     const { departements, ...dirData } = item;
// //     const dir = await Direction.create(dirData);
// //     console.log(`📁 ${dir.nom}`);
// //     for (const dep of departements) {
// //       await Departement.create({ ...dep, direction: dir._id });
// //       console.log(`   └── ${dep.nom}`);
// //     }
// //   }

// //   console.log('\n✅ Seed terminé !');
// //   await mongoose.connection.close();
// // };

// // run().catch(err => { console.error('❌', err.message); process.exit(1); });
// /**
//  * seed.js — Peuple DirectionCentrale + Direction + Departement
//  * Usage: node seed.js
//  */
// const dotenv = require('dotenv');
// dotenv.config({ path: './config.env' });

// const mongoose          = require('mongoose');
// const DirectionCentrale = require('./models/DirectionCentrale');
// const Direction         = require('./models/Direction');
// const Departement       = require('./models/Departement');

// const data = [
//   {
//     code:        'DCJ',
//     nom:         'DC Juridique',
//     description: 'Direction Centrale Juridique',
//     directions: [
//       {
//         code:        'DC',
//         nom:         'Direction Contrats',
//         description: 'Gestion et suivi des contrats',
//         departements: [
//           { code: 'DC-CONT', nom: 'Département Contrats',               description: 'Rédaction et suivi des contrats' },
//           { code: 'DC-AC',   nom: 'Département Assistance et Conseils', description: 'Assistance juridique et conseils' },
//           { code: 'DC-DL',   nom: 'Département Dépôt Légal',            description: 'Gestion du dépôt légal' },
//         ],
//       },
//       {
//         code:        'DRD',
//         nom:         'Direction Règlement des Différends',
//         description: 'Règlement amiable et judiciaire des différends',
//         departements: [
//           { code: 'DRD-CI',   nom: 'Département Contentieux Interne',       description: 'Traitement des contentieux internes' },
//           { code: 'DRD-CINT', nom: 'Département Contentieux International', description: 'Traitement des contentieux internationaux' },
//           { code: 'DRD-AL',   nom: 'Département Analyses des Litiges',      description: 'Analyse et suivi des litiges' },
//         ],
//       },
//       {
//         code:        'DER',
//         nom:         'Direction Études et Réglementation',
//         description: 'Veille juridique, études et réglementation',
//         departements: [
//           { code: 'DER-AJ',   nom: 'Département Analyses Juridiques',                          description: 'Analyses et avis juridiques' },
//           { code: 'DER-RVJ',  nom: 'Département Réglementation et Veille Juridique',           description: 'Veille réglementaire' },
//           { code: 'DER-SJOP', nom: 'Département Suivi Juridique des Opérations Patrimoniales', description: 'Suivi juridique des opérations patrimoniales' },
//         ],
//       },
//     ],
//   },
// ];

// const run = async () => {
//   await mongoose.connect(process.env.MONGODB_URI);
//   console.log('✅ MongoDB connecté\n');

//   // Nettoyage dans l'ordre enfant → parent
//   await Departement.deleteMany({});
//   await Direction.deleteMany({});
//   await DirectionCentrale.deleteMany({});
//   console.log('🗑️  Collections nettoyées\n');

//   for (const dcData of data) {
//     const { directions, ...dcFields } = dcData;

//     // 1. Créer la Direction Centrale
//     const dc = await DirectionCentrale.create(dcFields);
//     console.log(`🏛️  ${dc.nom} (${dc.code})`);

//     for (const dirData of directions) {
//       const { departements, ...dirFields } = dirData;

//       // 2. Créer la Direction liée à la DC
//       const dir = await Direction.create({ ...dirFields, directionCentrale: dc._id });
//       console.log(`  📁 ${dir.nom} (${dir.code})`);

//       for (const dep of departements) {
//         // 3. Créer le Département lié à la Direction
//         await Departement.create({ ...dep, direction: dir._id });
//         console.log(`     └── ${dep.nom}`);
//       }
//     }
//   }

//   console.log('\n✅ Seed terminé !');
//   await mongoose.connection.close();
// };

// run().catch(err => { console.error('❌', err.message); process.exit(1); });
/**
 * seed-activite-transport.js — Activité Transport par Canalisations
 * Usage: node seed-activite-transport.js
 */
// const dotenv = require('dotenv');
// dotenv.config({ path: './config.env' });

// const mongoose            = require('mongoose');
// const Activite            = require('./models/Activite');
// const DirectionActivite   = require('./models/DirectionActivite');
// const DepartementActivite = require('./models/DepartementActivite');
// const Division            = require('./models/Division');
// const Structure           = require('./models/Structure');

// // ─── DONNÉES ────────────────────────────────────────────────────────────────

// const activiteData = {
//   code:        'TRC',
//   nom:         'Transport par Canalisations',
//   description: 'Activité Transport par Canalisations',
// };

// const directionsData = [
//   {
//     code:        'TRC-DJ',
//     nom:         'Direction Juridique',
//     description: 'Direction Juridique de l\'activité Transport par Canalisations',
//     departements: [
//       {
//         code:        'TRC-DJ-DCR',
//         nom:         'Département Contrats et Réglementation',
//         description: 'Gestion des contrats et de la réglementation',
//       },
//       {
//         code:        'TRC-DJ-DC',
//         nom:         'Département Contentieux',
//         description: 'Traitement des contentieux',
//       },
//       {
//         code:        'TRC-DJ-DPA',
//         nom:         'Département Patrimoine et Assurances',
//         description: 'Gestion du patrimoine et des assurances',
//       },
//       {
//         code:        'TRC-DJ-DPC',
//         nom:         'Département Passation des Contrats',
//         description: 'Passation et suivi des contrats',
//       },
//     ],
//   },
//   {
//     code:        'TRC-DTEL',
//     nom:         'Direction Télécommunications',
//     description: 'Direction Télécommunications de l\'activité Transport par Canalisations',
//     departements: [],
//   },
// ];

// const divisionsData = [
//   {
//     code:        'TRC-DEXP',
//     nom:         'Division Exploitation',
//     description: 'Division en charge de l\'exploitation',
//     structures:  [],
//   },
//   {
//     code:        'TRC-DMAINT',
//     nom:         'Division Maintenance',
//     description: 'Division en charge de la maintenance',
//     structures:  [],
//   },
//   {
//     code:        'TRC-DESR',
//     nom:         'Division Études et Suivi des Réalisations',
//     description: 'Division en charge des études et du suivi des réalisations',
//     structures:  [],
//   },
// ];

// // ─── SCRIPT ─────────────────────────────────────────────────────────────────

// const run = async () => {
//   await mongoose.connect(process.env.MONGODB_URI);
//   console.log('✅ MongoDB connecté\n');

//   // Nettoyage ciblé (uniquement l'activité TRC)
//   const existing = await Activite.findOne({ code: 'TRC' });
//   if (existing) {
//     const dirs = await DirectionActivite.find({ activite: existing._id });
//     for (const dir of dirs) {
//       await DepartementActivite.deleteMany({ directionActivite: dir._id });
//     }
//     await DirectionActivite.deleteMany({ activite: existing._id });

//     const divs = await Division.find({ activite: existing._id });
//     for (const div of divs) {
//       await Structure.deleteMany({ division: div._id });
//     }
//     await Division.deleteMany({ activite: existing._id });
//     await Activite.deleteOne({ _id: existing._id });
//     console.log('🗑️  Anciennes données TRC nettoyées\n');
//   }

//   // 1. Créer l'Activité
//   const activite = await Activite.create(activiteData);
//   console.log(`🏭 Activité : ${activite.nom} (${activite.code})\n`);

//   // 2. Créer les Directions + Départements
//   console.log('📁 Directions :');
//   for (const dirData of directionsData) {
//     const { departements, ...dirFields } = dirData;
//     const dir = await DirectionActivite.create({ ...dirFields, activite: activite._id });
//     console.log(`  📂 ${dir.nom} (${dir.code})`);

//     for (const dep of departements) {
//       await DepartementActivite.create({ ...dep, directionActivite: dir._id });
//       console.log(`     └── ${dep.nom}`);
//     }
//   }

//   // 3. Créer les Divisions + Structures
//   console.log('\n🔷 Divisions :');
//   for (const divData of divisionsData) {
//     const { structures, ...divFields } = divData;
//     const div = await Division.create({ ...divFields, activite: activite._id });
//     console.log(`  🔹 ${div.nom} (${div.code})`);

//     for (const struct of structures) {
//       await Structure.create({ ...struct, division: div._id });
//       console.log(`     └── [${struct.type}] ${struct.nom}`);
//     }
//   }

//   console.log('\n✅ Seed Transport par Canalisations terminé !');
//   await mongoose.connection.close();
// };

// run().catch(err => {
//   console.error('❌', err.message);
//   process.exit(1);
// });

// const dotenv = require('dotenv');
// dotenv.config({ path: './config.env' });

// const mongoose          = require('mongoose');
// const DirectionCentrale = require('./models/DirectionCentrale');
// const Direction         = require('./models/Direction');
// const Departement       = require('./models/Departement');

// // ✅ DG statique — pas de modèle, juste une constante
// const DIRECTION_GENERALE = {
//   code:        'DGS',
//   nom:         'Direction Générale Sonatrach',
//   description: 'Présidence Directeur Général Sonatrach',
// };

// const data = [
//   {
//     code:        'DCJ',
//     nom:         'DC Juridique',
//     description: 'Direction Centrale Juridique',
//     directions: [
//       {
//         code:        'DC-CONT',
//         nom:         'Direction Contrats',
//         description: 'Gestion et suivi des contrats',
//         departements: [
//           { code: 'DC-CONT-D', nom: 'Département Contrats',               description: 'Rédaction et suivi des contrats' },
//           { code: 'DC-AC',     nom: 'Département Assistance et Conseils', description: 'Assistance juridique et conseils' },
//           { code: 'DC-DL',     nom: 'Département Dépôt Légal',            description: 'Gestion du dépôt légal' },
//         ],
//       },
//       {
//         code:        'DRD',
//         nom:         'Direction Règlement des Différends',
//         description: 'Règlement amiable et judiciaire des différends',
//         departements: [
//           { code: 'DRD-CI',   nom: 'Département Contentieux Interne',       description: 'Traitement des contentieux internes' },
//           { code: 'DRD-CINT', nom: 'Département Contentieux International', description: 'Traitement des contentieux internationaux' },
//           { code: 'DRD-AL',   nom: 'Département Analyses des Litiges',      description: 'Analyse et suivi des litiges' },
//         ],
//       },
//       {
//         code:        'DER',
//         nom:         'Direction Études et Réglementation',
//         description: 'Veille juridique, études et réglementation',
//         departements: [
//           { code: 'DER-AJ',   nom: 'Département Analyses Juridiques',                          description: 'Analyses et avis juridiques' },
//           { code: 'DER-RVJ',  nom: 'Département Réglementation et Veille Juridique',           description: 'Veille réglementaire' },
//           { code: 'DER-SJOP', nom: 'Département Suivi Juridique des Opérations Patrimoniales', description: 'Suivi juridique des opérations patrimoniales' },
//         ],
//       },
//     ],
//   },
//   {
//     code:        'DCFI',
//     nom:         'DCP Finances',
//     description: 'Direction Centrale Finances',
//     directions: [
//       {
//         code:        'DFI-BUD',
//         nom:         'Direction Budget',
//         description: 'Gestion budgétaire',
//         departements: [
//           { code: 'DFI-BUD-D', nom: 'Département Budget', description: 'Élaboration et suivi du budget' },
//         ],
//       },
//     ],
//   },
// ];

// const run = async () => {
//   await mongoose.connect(process.env.MONGODB_URI);
//   console.log('✅ MongoDB connecté\n');

//   await Departement.deleteMany({});
//   await Direction.deleteMany({});
//   await DirectionCentrale.deleteMany({});
//   console.log('🗑️  Collections nettoyées\n');

//   // Affichage statique de la DG
//   console.log(`🏢 [STATIQUE] ${DIRECTION_GENERALE.nom} (${DIRECTION_GENERALE.code})\n`);

//   for (const dcData of data) {
//     const { directions, ...dcFields } = dcData;

//     // 1. DirectionCentrale — on stocke le nom de la DG en string, pas d'ObjectId
//     const dc = await DirectionCentrale.create({
//       ...dcFields,
//       directionGenerale: DIRECTION_GENERALE.nom, // simple string
//     });
//     console.log(`  🏛️  ${dc.nom} (${dc.code})`);

//     for (const dirData of directions) {
//       const { departements, ...dirFields } = dirData;

//       // 2. Direction
//       const dir = await Direction.create({ ...dirFields, directionCentrale: dc._id });
//       console.log(`    📁 ${dir.nom} (${dir.code})`);

//       for (const dep of departements) {
//         // 3. Département
//         await Departement.create({ ...dep, direction: dir._id });
//         console.log(`       └── ${dep.nom}`);
//       }
//     }
//   }

//   console.log('\n✅ Seed terminé !');
//   await mongoose.connection.close();
// };

// run().catch(err => { console.error('❌', err.message); process.exit(1); });
/**
 * seed-activite-transport.js — Activité Transport par Canalisations
 * Usage: node seed-activite-transport.js
 */
const dotenv = require('dotenv');
dotenv.config({ path: './config.env' });

const mongoose            = require('mongoose');
const Activite            = require('./models/Activite');
const DirectionActivite   = require('./models/DirectionActivite');
const DepartementActivite = require('./models/DepartementActivite');
const Division            = require('./models/Division');
const Structure           = require('./models/Structure');

// ─── DONNÉES ────────────────────────────────────────────────────────────────

const activiteData = {
  code:        'TRC',
  nom:         'Transport par Canalisations',
  description: 'Activité Transport par Canalisations',
};

const directionsData = [
  {
    code:        'TRC-DJ',
    nom:         'Direction Juridique',
    description: 'Direction Juridique de l\'activité Transport par Canalisations',
    departements: [
      {
        code:        'TRC-DJ-DCR',
        nom:         'Département Contrats et Réglementation',
        description: 'Gestion des contrats et de la réglementation',
      },
      {
        code:        'TRC-DJ-DC',
        nom:         'Département Contentieux',
        description: 'Traitement des contentieux',
      },
      {
        code:        'TRC-DJ-DPA',
        nom:         'Département Patrimoine et Assurances',
        description: 'Gestion du patrimoine et des assurances',
      },
      {
        code:        'TRC-DJ-DPC',
        nom:         'Département Passation des Contrats',
        description: 'Passation et suivi des contrats',
      },
    ],
  },
  {
    code:        'TRC-DTEL',
    nom:         'Direction Télécommunications',
    description: 'Direction Télécommunications de l\'activité Transport par Canalisations',
    departements: [],
  },
];

const divisionsData = [
  {
    code:        'TRC-DEXP',
    nom:         'Division Exploitation',
    description: 'Division en charge de l\'exploitation',
    structures:  [],
  },
  {
    code:        'TRC-DMAINT',
    nom:         'Division Maintenance',
    description: 'Division en charge de la maintenance',
    structures:  [],
  },
  {
    code:        'TRC-DESR',
    nom:         'Division Études et Suivi des Réalisations',
    description: 'Division en charge des études et du suivi des réalisations',
    structures:  [],
  },
];

// ─── SCRIPT ─────────────────────────────────────────────────────────────────

const run = async () => {
  await mongoose.connect(process.env.MONGODB_URI);
  console.log('✅ MongoDB connecté\n');

  // Nettoyage ciblé (uniquement l'activité TRC)
  const existing = await Activite.findOne({ code: 'TRC' });
  if (existing) {
    const dirs = await DirectionActivite.find({ activite: existing._id });
    for (const dir of dirs) {
      await DepartementActivite.deleteMany({ directionActivite: dir._id });
    }
    await DirectionActivite.deleteMany({ activite: existing._id });

    const divs = await Division.find({ activite: existing._id });
    for (const div of divs) {
      await Structure.deleteMany({ division: div._id });
    }
    await Division.deleteMany({ activite: existing._id });
    await Activite.deleteOne({ _id: existing._id });
    console.log('🗑️  Anciennes données TRC nettoyées\n');
  }

  // 1. Créer l'Activité
  const activite = await Activite.create(activiteData);
  console.log(`🏭 Activité : ${activite.nom} (${activite.code})\n`);

  // 2. Créer les Directions + Départements
  console.log('📁 Directions :');
  for (const dirData of directionsData) {
    const { departements, ...dirFields } = dirData;
    const dir = await DirectionActivite.create({ ...dirFields, activite: activite._id });
    console.log(`  📂 ${dir.nom} (${dir.code})`);

    for (const dep of departements) {
      await DepartementActivite.create({ ...dep, directionActivite: dir._id });
      console.log(`     └── ${dep.nom}`);
    }
  }

  // 3. Créer les Divisions + Structures
  console.log('\n🔷 Divisions :');
  for (const divData of divisionsData) {
    const { structures, ...divFields } = divData;
    const div = await Division.create({ ...divFields, activite: activite._id });
    console.log(`  🔹 ${div.nom} (${div.code})`);

    for (const struct of structures) {
      await Structure.create({ ...struct, division: div._id });
      console.log(`     └── [${struct.type}] ${struct.nom}`);
    }
  }

  console.log('\n✅ Seed Transport par Canalisations terminé !');
  await mongoose.connection.close();
};

run().catch(err => {
  console.error('❌', err.message);
  process.exit(1);
});
