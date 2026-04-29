const mongoose = require("mongoose");
const dotenv = require("dotenv");
const app = require("./app");

dotenv.config();

mongoose
  .connect(process.env.MONGO_URI)
  .then(() => console.log("Connected to MongoDB successfully"))
  .catch((err) => console.error("MongoDB error:", err));

const PORT = process.env.PORT || 4003;
app.listen(PORT, () => {
  console.log(`Order Service is running on port ${PORT}`);
});
