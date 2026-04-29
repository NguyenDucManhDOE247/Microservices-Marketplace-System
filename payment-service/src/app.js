const express = require("express");
const cors = require("cors");
const paymentRoutes = require("./routes/payment.routes");

const app = express();
app.use(cors());
app.use(express.json());

app.use("/api/payments", paymentRoutes);

module.exports = app;
