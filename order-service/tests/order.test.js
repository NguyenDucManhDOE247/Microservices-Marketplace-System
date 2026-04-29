const request = require("supertest");
const mongoose = require("mongoose");
const { MongoMemoryServer } = require("mongodb-memory-server");
const axios = require("axios");

// Mock axios so order-service does not call real user-service
jest.mock("axios");

let mongoServer;
let app;

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
  jest.clearAllMocks();
  const collections = mongoose.connection.collections;
  for (const key in collections) {
    await collections[key].deleteMany({});
  }
});

describe("POST /api/orders", () => {
  it("should create an order when user exists", async () => {
    axios.get.mockResolvedValue({ data: { exists: true } });

    const res = await request(app).post("/api/orders").send({
      userEmail: "user@example.com",
      productId: new mongoose.Types.ObjectId().toString(),
      quantity: 2,
      totalPrice: 1000,
    });

    expect(res.status).toBe(201);
    expect(res.body.userEmail).toBe("user@example.com");
    expect(res.body.quantity).toBe(2);
    expect(res.body._id).toBeDefined();
  });

  it("should return 400 when user does not exist", async () => {
    axios.get.mockResolvedValue({ data: { exists: false } });

    const res = await request(app).post("/api/orders").send({
      userEmail: "ghost@example.com",
      productId: new mongoose.Types.ObjectId().toString(),
      quantity: 1,
      totalPrice: 500,
    });

    expect(res.status).toBe(400);
    expect(res.body.error).toBe("User email does not exist!");
  });

  it("should return 500 when user-service is unreachable", async () => {
    axios.get.mockRejectedValue(new Error("ECONNREFUSED"));

    const res = await request(app).post("/api/orders").send({
      userEmail: "user@example.com",
      productId: new mongoose.Types.ObjectId().toString(),
      quantity: 1,
      totalPrice: 500,
    });

    expect(res.status).toBe(500);
  });
});

describe("GET /api/orders", () => {
  beforeEach(async () => {
    axios.get.mockResolvedValue({ data: { exists: true } });
    await request(app)
      .post("/api/orders")
      .send({ userEmail: "a@example.com", productId: "p1", quantity: 1, totalPrice: 100 });
  });

  it("should return all orders", async () => {
    const res = await request(app).get("/api/orders");

    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    expect(res.body.length).toBeGreaterThan(0);
  });
});

describe("GET /api/orders/user/:email", () => {
  beforeEach(async () => {
    axios.get.mockResolvedValue({ data: { exists: true } });
    await request(app)
      .post("/api/orders")
      .send({ userEmail: "filter@example.com", productId: "p2", quantity: 3, totalPrice: 300 });
    await request(app)
      .post("/api/orders")
      .send({ userEmail: "other@example.com", productId: "p3", quantity: 1, totalPrice: 100 });
  });

  it("should return only orders for specified email", async () => {
    const res = await request(app).get("/api/orders/user/filter@example.com");

    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    expect(res.body.every((o) => o.userEmail === "filter@example.com")).toBe(true);
  });
});

describe("GET /api/orders/:id", () => {
  let orderId;

  beforeEach(async () => {
    axios.get.mockResolvedValue({ data: { exists: true } });
    const res = await request(app)
      .post("/api/orders")
      .send({ userEmail: "id@example.com", productId: "p4", quantity: 1, totalPrice: 200 });
    orderId = res.body._id;
  });

  it("should return an order by ID", async () => {
    const res = await request(app).get(`/api/orders/${orderId}`);

    expect(res.status).toBe(200);
    expect(res.body._id).toBe(orderId);
  });

  it("should return 404 for non-existent ID", async () => {
    const fakeId = new mongoose.Types.ObjectId().toString();
    const res = await request(app).get(`/api/orders/${fakeId}`);

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
