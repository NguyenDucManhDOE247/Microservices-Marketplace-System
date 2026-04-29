const express = require("express");
const router = express.Router();
const { body } = require("express-validator");
const controller = require("../controllers/order.controller");
const auth = require("../middleware/auth");

const orderValidation = [
  body("productId").notEmpty().withMessage("productId is required"),
  body("quantity")
    .isInt({ gt: 0, max: 9999 })
    .withMessage("quantity must be a positive integer no greater than 9999"),
  body("totalPrice")
    .isNumeric()
    .withMessage("totalPrice must be a number")
    .isFloat({ gt: 0, max: 100000000 })
    .withMessage("totalPrice must be between 0 and 100,000,000"),
];

router.post("/", auth, orderValidation, controller.createOrder);
router.get("/", controller.getAllOrders);
router.get("/user/:email", controller.getOrdersByUser);
router.get("/:id", controller.getOrderById);

module.exports = router;
