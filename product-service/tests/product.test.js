const request = require("supertest");
const mongoose = require("mongoose");
const { MongoMemoryServer } = require("mongodb-memory-server");

let mongoServer;
let app;
let createdProductId;

beforeAll(async () => {
  mongoServer = await MongoMemoryServer.create();
  await mongoose.connect(mongoServer.getUri());
  app = require("../src/app");
});

afterAll(async () => {
  await mongoose.disconnect();
  await mongoServer.stop();
});

afterEach(async () => {
  const collections = mongoose.connection.collections;
  for (const key in collections) {
    await collections[key].deleteMany({});
  }
});

describe("POST /api/products", () => {
  it("should create a product and return 201", async () => {
    const res = await request(app)
      .post("/api/products")
      .send({ name: "Test Service", price: 100, description: "A test service", category: "Test" });

    expect(res.status).toBe(201);
    expect(res.body.name).toBe("Test Service");
    expect(res.body._id).toBeDefined();
    createdProductId = res.body._id;
  });
});

describe("GET /api/products", () => {
  beforeEach(async () => {
    await request(app)
      .post("/api/products")
      .send({ name: "Service A", price: 200, description: "Service A desc", category: "Web" });
  });

  it("should return an array of products", async () => {
    const res = await request(app).get("/api/products");

    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    expect(res.body.length).toBeGreaterThan(0);
  });
});

describe("GET /api/products/:id", () => {
  let productId;

  beforeEach(async () => {
    const res = await request(app)
      .post("/api/products")
      .send({ name: "Single Service", price: 300, description: "desc", category: "Backend" });
    productId = res.body._id;
  });

  it("should return a product by ID", async () => {
    const res = await request(app).get(`/api/products/${productId}`);

    expect(res.status).toBe(200);
    expect(res.body._id).toBe(productId);
  });

  it("should return 404 for invalid ID", async () => {
    const fakeId = new mongoose.Types.ObjectId().toString();
    const res = await request(app).get(`/api/products/${fakeId}`);

    expect(res.status).toBe(404);
  });
});

describe("PUT /api/products/:id", () => {
  let productId;

  beforeEach(async () => {
    const res = await request(app)
      .post("/api/products")
      .send({ name: "Old Name", price: 400, description: "old desc", category: "Mobile" });
    productId = res.body._id;
  });

  it("should update a product price", async () => {
    const res = await request(app).put(`/api/products/${productId}`).send({ price: 999 });

    expect(res.status).toBe(200);
    expect(res.body.price).toBe(999);
  });
});

describe("DELETE /api/products/:id", () => {
  let productId;

  beforeEach(async () => {
    const res = await request(app)
      .post("/api/products")
      .send({ name: "To Delete", price: 500, description: "bye", category: "Design" });
    productId = res.body._id;
  });

  it("should delete a product and return success message", async () => {
    const res = await request(app).delete(`/api/products/${productId}`);

    expect(res.status).toBe(200);
    expect(res.body.message).toBe("Product deleted");
  });

  it("should return 404 after deletion", async () => {
    await request(app).delete(`/api/products/${productId}`);
    const res = await request(app).get(`/api/products/${productId}`);

    expect(res.status).toBe(404);
  });
});

describe("GET /metrics", () => {
  it("should return Prometheus metrics in text format", async () => {
    const res = await request(app).get("/metrics");

    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toMatch(/text\/plain/);
    expect(res.text).toContain("http_requests_total");
  });

  it("should return 404 for unknown routes", async () => {
    const res = await request(app).get("/unknown-route-xyz");

    expect(res.status).toBe(404);
    expect(res.body.error).toBe("Not found");
  });
});
