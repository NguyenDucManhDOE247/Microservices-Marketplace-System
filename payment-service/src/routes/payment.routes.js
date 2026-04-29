const express = require("express");
const router = express.Router();
const { body } = require("express-validator");
const { processPayment } = require("../controllers/payment.controller");
const auth = require("../middleware/auth");

const paymentValidation = [
  body("orderId").notEmpty().withMessage("orderId is required"),
  body("amount")
    .isNumeric()
    .withMessage("amount must be a number")
    .isFloat({ gt: 0 })
    .withMessage("amount must be greater than 0"),
];

router.post("/", auth, paymentValidation, processPayment);

router.get("/", (req, res) => {
  res.json([{ status: "paid", orderId: "example123" }]);
});

module.exports = router;
