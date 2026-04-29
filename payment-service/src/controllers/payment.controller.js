const Payment = require("../models/payment.model");
const { validationResult } = require("express-validator");

exports.processPayment = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(422).json({ errors: errors.array() });
  }

  const { orderId, amount } = req.body;
  const userEmail = req.user.email;

  try {
    const payment = new Payment({ orderId, amount, userEmail });
    await payment.save();
    res.json({
      message: "Payment successful",
      orderId,
      amount,
      status: "paid",
      paidAt: payment.paidAt,
    });
  } catch (err) {
    console.error("Payment error:", err.message);
    res.status(500).json({ error: "Server error" });
  }
};
