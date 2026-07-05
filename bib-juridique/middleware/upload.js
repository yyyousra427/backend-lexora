const multer = require("multer");
const path = require("path");
const fs = require("fs");

const uploadDir = "src/uploads";

if (!fs.existsSync(uploadDir)) {
    fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({

    destination: (req, file, cb) => {
        cb(null, uploadDir);
    },

    filename: (req, file, cb) => {

        const uniqueName =
            Date.now() +
            "-" +
            Math.round(Math.random() * 1E9);

        cb(
            null,
            uniqueName + path.extname(file.originalname)
        );
    }
});

const fileFilter = (req, file, cb) => {

    if (
        file.mimetype === "application/pdf"
    ) {
        cb(null, true);
    } else {
        cb(
            new Error(
                "Seuls les fichiers PDF sont autorisés"
            ),
            false
        );
    }
};

module.exports = multer({
    storage,
    fileFilter,
    limits: {
        fileSize: 20 * 1024 * 1024
    }
});