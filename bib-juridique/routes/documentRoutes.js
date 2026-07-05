const express = require("express");

const router = express.Router();
const upload = require("../middleware/upload");

const {
    createDocument,
    getAllDocuments,
    getDocumentById,
    updateDocument,
    deleteDocument,
    searchDocuments
} = require("../controllers/documentController");

// ==========================
// CREATE DOCUMENT
// POST /bib/documents
// ==========================
// router.post(
//     "/documents",
//     createDocument
// );
router.post(
    "/documents",
    upload.single("pdf"),
    createDocument
);

// ==========================
// GET ALL DOCUMENTS
// GET /bib/documents
// ==========================
router.get(
    "/documents",
    getAllDocuments
);

// ==========================
// SEARCH DOCUMENTS
// GET /bib/search?q=...
// ==========================
router.get(
    "/search",
    searchDocuments
);

// ==========================
// GET DOCUMENT BY ID
// GET /bib/documents/:id
// ==========================
router.get(
    "/documents/:id",
    getDocumentById
);

// ==========================
// UPDATE DOCUMENT
// PUT /bib/documents/:id
// ==========================
// router.put(
//     "/documents/:id",
//     updateDocument
// );
router.put(
    "/documents/:id",
    upload.single("pdf"),
    updateDocument
);

// ==========================
// DELETE DOCUMENT
// DELETE /bib/documents/:id
// ==========================
router.delete(
    "/documents/:id",
    deleteDocument
);

module.exports = router;