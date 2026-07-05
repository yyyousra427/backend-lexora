const mongoose = require("mongoose");

const documentJuridiqueSchema = new mongoose.Schema(
{
    titre: {
        type: String,
        required: true
    },

    categorie: {
        type: String,
        enum: [
            "CONSTITUTION",
            "TRAITES_ET_ACCORDS",
            "LOIS",
            "ORDONNANCES",
            "DECRETS",
            "DECISIONS_ET_ARRETES",
            "TEXTES_REGLEMENTAIRES",
            "CONTRATS_ET_MODELES",
            "DOCUMENTATION_INTERNE",
            "JURISPRUDENCE"
        ],
        required: true
    },

    reference: {
        type: String
    },

    organismeEmetteur: {
        type: String
    },

    datePublication: {
        type: Date
    },

    motsCles: [{
        type: String
    }],

    resume: {
        type: String
    },

    statut: {
        type: String,
        enum: [
            "EN_VIGUEUR",
            "ABROGE",
            "MODIFIE"
        ],
        default: "EN_VIGUEUR"
    },

    pdfUrl: {
        type: String,
        required: true
    },

    uploadedBy: {
        type: String
    }
},
{
    timestamps: true
});

module.exports = mongoose.model(
    "DocumentJuridique",
    documentJuridiqueSchema
);