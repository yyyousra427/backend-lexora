// bib-juridique/fix-document-urls.js
const mongoose = require("mongoose");
const fs = require("fs");
const path = require("path");

// Modèle DocumentJuridique
const DocumentJuridique = require("./models/DocumentJuridique");

const MONGODB_URI = "mongodb://root:root@localhost:27017/bib_juridique_db?authSource=admin";

const fixDocumentUrls = async () => {
    try {
        await mongoose.connect(MONGODB_URI);
        console.log("✅ Connecté à MongoDB\n");

        // Lire tous les fichiers dans le dossier uploads
        const uploadsDir = path.join(__dirname, "src/uploads");
        const files = fs.readdirSync(uploadsDir);
        console.log("📄 Fichiers disponibles dans uploads:");
        files.forEach(f => console.log(`   - ${f}`));
        console.log("");

        // Récupérer tous les documents
        const documents = await DocumentJuridique.find({});
        console.log(`📚 ${documents.length} documents trouvés dans MongoDB\n`);

        let fixedCount = 0;

        for (const doc of documents) {
            console.log(`📝 Document: ${doc.titre}`);
            console.log(`   ID: ${doc._id}`);
            console.log(`   Ancien pdfUrl: ${doc.pdfUrl}`);
            
            // Vérifier si le pdfUrl est correct
            let needsUpdate = false;
            let newPdfUrl = doc.pdfUrl;
            
            // Cas 1: L'URL pointe vers un fichier qui n'existe pas
            if (doc.pdfUrl) {
                const filename = doc.pdfUrl.split('/').pop();
                if (filename && !files.includes(filename)) {
                    console.log(`   ⚠️ Fichier '${filename}' non trouvé dans uploads`);
                    
                    // Chercher un fichier qui pourrait correspondre
                    // Par ordre de priorité: par titre, ou le plus récent
                    let foundFile = null;
                    
                    // Nettoyer le titre pour la recherche
                    const cleanTitle = doc.titre.toLowerCase().replace(/[^a-z0-9]/g, '');
                    
                    // Chercher un fichier qui contient le titre
                    for (const file of files) {
                        if (file.toLowerCase().includes(cleanTitle) || 
                            (doc.reference && file.includes(doc.reference))) {
                            foundFile = file;
                            break;
                        }
                    }
                    
                    // Si pas trouvé, prendre le fichier le plus récent
                    if (!foundFile && files.length > 0) {
                        // Trier par date de création (du plus récent au plus ancien)
                        const sortedFiles = files.sort((a, b) => {
                            const statA = fs.statSync(path.join(uploadsDir, a));
                            const statB = fs.statSync(path.join(uploadsDir, b));
                            return statB.mtimeMs - statA.mtimeMs;
                        });
                        foundFile = sortedFiles[0];
                        console.log(`   📌 Utilisation du fichier le plus récent: ${foundFile}`);
                    }
                    
                    if (foundFile) {
                        newPdfUrl = `/uploads/${foundFile}`;
                        needsUpdate = true;
                        console.log(`   ✅ Nouveau pdfUrl: ${newPdfUrl}`);
                    }
                } else if (filename && files.includes(filename)) {
                    console.log(`   ✅ Fichier trouvé: ${filename}`);
                }
            }
            
            // Mettre à jour si nécessaire
            if (needsUpdate) {
                doc.pdfUrl = newPdfUrl;
                await doc.save();
                fixedCount++;
                console.log(`   💾 Mis à jour\n`);
            } else {
                console.log(`   ✅ Déjà correct\n`);
            }
        }
        
        console.log("=".repeat(50));
        console.log(`✅ Migration terminée ! ${fixedCount} documents corrigés`);
        
        // Afficher le résumé
        const updatedDocs = await DocumentJuridique.find({});
        console.log("\n📊 Résumé des documents après correction:");
        updatedDocs.forEach(doc => {
            console.log(`   - ${doc.titre}: ${doc.pdfUrl}`);
        });
        
        await mongoose.disconnect();
        console.log("\n✅ Déconnecté de MongoDB");
        
    } catch (error) {
        console.error("❌ Erreur:", error);
    }
};

// Exécuter le script
fixDocumentUrls();