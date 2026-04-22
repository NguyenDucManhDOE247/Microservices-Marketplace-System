const User = require("../models/user.model");
const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");

exports.register = async (req, res) => {
  try {
    const { email, password } = req.body;

    const existingUser = await User.findOne({ email });
    if (existingUser) return res.status(400).json({ error: "Email already exists" });

    const hashed = await bcrypt.hash(password, 10);
    const user = new User({ email, password: hashed });
    await user.save();
    res.json({ message: "Registration successful" });
  } catch (err) {
    console.error("Register error:", err.message);
    res.status(500).json({ error: "Server error" });
  }
};

exports.login = async (req, res) => {
  try {
    const { email, password } = req.body;
    const user = await User.findOne({ email });
    if (!user) return res.status(400).json({ error: "User not found" });

    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) return res.status(401).json({ error: "Incorrect password" });

    const token = jwt.sign({ id: user._id, email: user.email }, process.env.JWT_SECRET || "fallback-secret");
    res.json({ message: "Login successful", token });
  } catch (err) {
    console.error("Login error:", err.message);
    res.status(500).json({ error: "Server error" });
  }
};

exports.checkEmail = async (req, res) => {
  const { email } = req.params;
  const user = await User.findOne({ email });
  if (!user) return res.status(404).json({ exists: false });
  res.json({ exists: true });
};
