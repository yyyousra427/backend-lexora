const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');
const notificationRoutes = require('./routes/notificationRoutes');
const riskAlertRoutes = require('./routes/riskAlerts');

const { authMiddleware } = require('./middleware/auth');

dotenv.config();

const app = express();

// Middleware
app.use(cors({
    origin: [
        'http://localhost:3000',
        'http://localhost:8083',
        'https://lexora-dz.netlify.app',
        // Front local en dev : tout port localhost (Vite 5173, CRA 3000, Angular 4200...)
        /^http:\/\/localhost:\d+$/,
        /^http:\/\/127\.0\.0\.1:\d+$/,
    ],
    credentials: true
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use('/notifications/risk-alerts', riskAlertRoutes);


// Routes (protégées par auth) - sans préfixe /api car le gateway gère
app.use('/notifications', authMiddleware, notificationRoutes);

// Health check pour Eureka
app.get('/health', (req, res) => {
    res.status(200).json({ status: 'UP', service: 'notification' });
});

module.exports = app;