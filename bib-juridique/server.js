require("dotenv").config({
    path: "./config.env"
});

const app =
require("./app");

const connectDB =
require("./config/database");

const {
    startEureka,
    stopEureka
} = require("./services/eurekaService");


// MongoDB

connectDB();


// Start Server

const PORT =
process.env.PORT || 8085;

const server =
app.listen(PORT, () => {

    console.log(
        `🚀 bib-juridique démarré sur ${PORT}`
    );

    startEureka();
});


// Graceful shutdown

process.on(
    "SIGINT",
    () => {

        stopEureka();

        server.close(() => {

            console.log(
                "🛑 Serveur arrêté"
            );

            process.exit(0);
        });
    }
);