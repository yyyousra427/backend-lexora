const express = require('express');
const cors    = require('cors');
const morgan  = require('morgan');

const directionRoutes   = require('./routes/directionRoutes');
const departementRoutes = require('./routes/departementRoutes');
const errorHandler      = require('./middleware/errorHandler');
const activiteRoutes = require('./routes/activiteRoutes');
const directions_centrales= require('./routes/directionCentraleRoutes');
const structureRoute = require('./routes/structureRoutes');
const divisionRoute= require('./routes/divisionRoutes');
const direction_activiteRoutes = require('./routes/directionActiviteRoutes');
const departemet_activiteRoute= require('./routes/departementActiviteRoutes');



const app = express();

app.use(cors());
app.use(express.json());
app.use(morgan('dev'));

app.get('/health', (req, res) => res.json({ status: 'UP', service: 'service-juridique' }));
app.get('/info',   (req, res) => res.json({ app: 'service-juridique' }));


app.use('/juridique/directions',   directionRoutes);
app.use('/juridique/departements', departementRoutes);
app.use('/juridique/activites', activiteRoutes);
app.use('/juridique/directions-centrales',directions_centrales)
app.use('/juridique/structure',   structureRoute);
app.use('/juridique/division', divisionRoute);
app.use('/juridique/direction_activite', direction_activiteRoutes);
app.use('/juridique/departemet_activite',departemet_activiteRoute)// role nesxiste pas

app.use((req, res) => {
  res.status(404).json({ success: false, message: `Route ${req.originalUrl} non trouvée` });
});

app.use(errorHandler);

module.exports = app;