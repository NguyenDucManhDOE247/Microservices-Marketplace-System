const express = require("express");
const router = express.Router();
const controller = require("../controllers/order.controller");

router.post("/", controller.createOrder);
router.get("/", controller.getAllOrders);
router.get("/user/:email", controller.getOrdersByUser);
router.get("/:id", controller.getOrderById);

module.exports = router;
