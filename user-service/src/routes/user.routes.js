const express = require("express");
const router = express.Router();
const { body } = require("express-validator");
const { register, login, checkEmail } = require("../controllers/user.controller");

const registerValidation = [
  body("email").isEmail().withMessage("Valid email is required"),
  body("password").isLength({ min: 6 }).withMessage("Password must be at least 6 characters"),
];

const loginValidation = [
  body("email").isEmail().withMessage("Valid email is required"),
  body("password").notEmpty().withMessage("Password is required"),
];

router.post("/register", registerValidation, register);
router.post("/login", loginValidation, login);
router.get("/check/:email", checkEmail);

router.get("/", (req, res) => {
  res.json([{ id: 1, email: "demo@user.com" }]);
});

module.exports = router;
