const mongoose = require("mongoose");

const paymentSchema = new mongoose.Schema({
  orderId: { type: String, required: true },
  amount: { type: Number, required: true },
  userEmail: { type: String, required: true },
  status: { type: String, default: "paid" },
  paidAt: { type: Date, default: Date.now },
});

module.exports = mongoose.model("Payment", paymentSchema);
