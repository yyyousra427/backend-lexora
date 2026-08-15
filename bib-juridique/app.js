// 
// bib-juridique/app.js
const express = require("express");
const cors = require("cors");
const path = require("path");
const fs = require("fs");

const documentRoutes = require("./routes/documentRoutes");

const app = express();

// Configuration CORS
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Servir les fichiers statiques du dossier uploads
const uploadsPath = path.join(__dirname, "src/uploads");
console.log("📁 Uploads directory:", uploadsPath);
console.log("📁 Exists:", fs.existsSync(uploadsPath));

if (fs.existsSync(uploadsPath)) {
    const files = fs.readdirSync(uploadsPath);
    console.log("📄 Files in uploads:", files);
}

// ⭐ CRUCIAL - Servir les fichiers statiques
app.use("/uploads", express.static(uploadsPath));

// Health check
app.get("/health", (req, res) => {
    let uploadsCount = 0;
    try { uploadsCount = fs.readdirSync(uploadsPath).length; } catch (e) { /* dossier absent */ }
    res.json({
        success: true,
        service: "bib-juridique",
        status: "UP",
        uploads: uploadsCount
    });
});

// Routes
app.use("/bib", documentRoutes);

// 404 handler
app.use((req, res) => {
    res.status(404).json({
        success: false,
        message: `Route introuvable: ${req.method} ${req.url}`
    });
});

module.exports = app;