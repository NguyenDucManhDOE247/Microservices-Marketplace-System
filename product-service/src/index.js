const mongoose = require("mongoose");
const dotenv = require("dotenv");
const app = require("./app");
const Product = require("./models/product.model");

dotenv.config();

mongoose
  .connect(process.env.MONGO_URI)
  .then(async () => {
    console.log("✅ Connected to MongoDB successfully");

    const count = await Product.estimatedDocumentCount();
    if (count === 0) {
      await Product.insertMany([
        {
          name: "Web Development",
          description: "Design and develop modern responsive websites",
          price: 500,
          category: "Web",
        },
        {
          name: "Mobile App Development",
          description: "Build Android and iOS apps, either native or cross-platform",
          price: 800,
          category: "Mobile",
        },
        {
          name: "UI/UX Design",
          description: "Design beautiful and user-friendly interfaces",
          price: 400,
          category: "Design",
        },
        {
          name: "Backend API Development",
          description: "Build RESTful API systems with Node.js",
          price: 600,
          category: "Backend",
        },
        {
          name: "DevOps Setup",
          description: "CI/CD, Docker, Kubernetes, optimize system operations",
          price: 700,
          category: "Infrastructure",
        },
      ]);
      console.log("✅ Seeded 5 sample services into MongoDB");
    }
  })
  .catch((err) => console.error("❌ MongoDB Error:", err));

const PORT = process.env.PORT || 4002;
app.listen(PORT, () => {
  console.log(`Product Service is running on port ${PORT}`);
});
