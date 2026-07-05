const DocumentJuridique =
require("../models/DocumentJuridique");


// ======================
// CREATE DOCUMENT
// ======================

// exports.createDocument = async (req, res) => {

//     try {

//         const document =
//             await DocumentJuridique.create({

//                 titre: req.body.titre,

//                 categorie:
//                     req.body.categorie,

//                 reference:
//                     req.body.reference,

//                 organismeEmetteur:
//                     req.body.organismeEmetteur,

//                 datePublication:
//                     req.body.datePublication,

//                 motsCles:
//                     req.body.motsCles
//                         ? req.body.motsCles.split(",")
//                         : [],

//                 resume:
//                     req.body.resume,

//                 statut:
//                     req.body.statut,

//                 pdfUrl:
//                     req.file
//                         ? req.file.path
//                         : null,

//                 uploadedBy:
//                     req.user?.id
//             });

//         res.status(201).json({
//             success: true,
//             data: document
//         });

//     } catch (error) {

//         res.status(500).json({
//             success: false,
//             message: error.message
//         });
//     }
// };


// ======================
// GET ALL
// ======================

exports.getAllDocuments =
async (req, res) => {

    try {

        const page =
            parseInt(req.query.page) || 1;

        const limit =
            parseInt(req.query.limit) || 10;

        const skip =
            (page - 1) * limit;

        const filter = {};

        if (req.query.categorie) {

            filter.categorie =
                req.query.categorie;
        }

        const documents =
            await DocumentJuridique
                .find(filter)
                .sort({
                    createdAt: -1
                })
                .skip(skip)
                .limit(limit);

        const total =
            await DocumentJuridique
                .countDocuments(filter);

        res.json({
            success: true,
            page,
            total,
            data: documents
        });

    } catch (error) {

        res.status(500).json({
            success: false,
            message: error.message
        });
    }
};


// ======================
// GET ONE
// ======================

exports.getDocumentById =
async (req, res) => {

    try {

        const document =
            await DocumentJuridique.findById(
                req.params.id
            );

        if (!document) {

            return res.status(404).json({
                success: false,
                message:
                    "Document introuvable"
            });
        }

        res.json({
            success: true,
            data: document
        });

    } catch (error) {

        res.status(500).json({
            success: false,
            message: error.message
        });
    }
};


// ======================
// UPDATE
// ======================

exports.updateDocument =
async (req, res) => {

    try {

        const document =
            await DocumentJuridique.findById(
                req.params.id
            );

        if (!document) {

            return res.status(404).json({
                success: false,
                message:
                    "Document introuvable"
            });
        }

        document.titre =
            req.body.titre ||
            document.titre;

        document.categorie =
            req.body.categorie ||
            document.categorie;

        document.reference =
            req.body.reference ||
            document.reference;

        document.organismeEmetteur =
            req.body.organismeEmetteur ||
            document.organismeEmetteur;

        document.datePublication =
            req.body.datePublication ||
            document.datePublication;

        document.resume =
            req.body.resume ||
            document.resume;

        document.statut =
            req.body.statut ||
            document.statut;

        if (req.file) {
            document.pdfUrl =
                req.file.path;
        }

        await document.save();

        res.json({
            success: true,
            data: document
        });

    } catch (error) {

        res.status(500).json({
            success: false,
            message: error.message
        });
    }
};


// ======================
// DELETE
// ======================

exports.deleteDocument =
async (req, res) => {

    try {

        const document =
            await DocumentJuridique.findById(
                req.params.id
            );

        if (!document) {

            return res.status(404).json({
                success: false,
                message:
                    "Document introuvable"
            });
        }

        await document.deleteOne();

        res.json({
            success: true,
            message:
                "Document supprimé"
        });

    } catch (error) {

        res.status(500).json({
            success: false,
            message: error.message
        });
    }
};


// ======================
// SEARCH
// ======================

exports.searchDocuments =
async (req, res) => {

    try {

        const keyword =
            req.query.q || "";

        const documents =
            await DocumentJuridique.find({

                $or: [

                    {
                        titre: {
                            $regex: keyword,
                            $options: "i"
                        }
                    },

                    {
                        reference: {
                            $regex: keyword,
                            $options: "i"
                        }
                    },

                    {
                        resume: {
                            $regex: keyword,
                            $options: "i"
                        }
                    }
                ]
            });

        res.json({
            success: true,
            total: documents.length,
            data: documents
        });

    } catch (error) {

        res.status(500).json({
            success: false,
            message: error.message
        });
    }
};
exports.createDocument = async (req, res) => {
    try {

        console.log("BODY =", req.body);
        console.log("FILE =", req.file);

        const document = await DocumentJuridique.create({

            titre: req.body.titre,

            categorie: req.body.categorie,

            reference: req.body.reference,

            organismeEmetteur:
                req.body.organismeEmetteur,

            datePublication:
                req.body.datePublication,

            motsCles: Array.isArray(req.body.motsCles)
                ? req.body.motsCles
                : req.body.motsCles
                    ? req.body.motsCles.split(",")
                    : [],

            resume: req.body.resume,

            statut: req.body.statut,

            // pdfUrl:
            //     req.file
            //         ? req.file.path
            //         : req.body.pdfUrl || null,
            pdfUrl:
    req.file
        ? `/uploads/${req.file.filename}`
        : null,

            uploadedBy:
                req.user?.id || null
        });

        res.status(201).json({
            success: true,
            data: document
        });

    } catch (error) {

        console.error(error);

        res.status(500).json({
            success: false,
            message: error.message
        });
    }
};