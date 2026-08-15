const express = require("express");

const router = express.Router();
const upload = require("../middleware/upload");
const { authMiddleware, checkRole } = require("../middleware/auth");

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
router.post(
    "/documents",
    authMiddleware,
    upload.single("pdf"),
    createDocument
);

// ==========================
// GET ALL DOCUMENTS
// GET /bib/documents
// ==========================
router.get(
    "/documents",
    authMiddleware,
    getAllDocuments
);

// ==========================
// SEARCH DOCUMENTS
// GET /bib/search?q=...
// ==========================
router.get(
    "/search",
    authMiddleware,
    searchDocuments
);

// ==========================
// GET DOCUMENT BY ID
// GET /bib/documents/:id
// ==========================
router.get(
    "/documents/:id",
    authMiddleware,
    getDocumentById
);

// ==========================
// UPDATE DOCUMENT
// PUT /bib/documents/:id
// ==========================
router.put(
    "/documents/:id",
    authMiddleware,
    upload.single("pdf"),
    updateDocument
);

// ==========================
// DELETE DOCUMENT (admin uniquement)
// DELETE /bib/documents/:id
// ==========================
router.delete(
    "/documents/:id",
    authMiddleware,
    checkRole("admin"),
    deleteDocument
);

module.exports = router;