const mongoose = require("mongoose");
const dotenv = require("dotenv");
const app = require("./app");

dotenv.config();

mongoose
  .connect(process.env.MONGO_URI)
  .then(() => console.log("Connected to MongoDB successfully"))
  .catch((err) => console.error("MongoDB error:", err));

const PORT = process.env.PORT || 4004;
app.listen(PORT, () => {
  console.log(`Payment Service is running on port ${PORT}`);
});
