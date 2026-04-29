const request = require("supertest");
const mongoose = require("mongoose");
const { MongoMemoryServer } = require("mongodb-memory-server");
const jwt = require("jsonwebtoken");

let mongoServer;
let app;

const TEST_EMAIL = "payer@example.com";
const validToken = jwt.sign({ id: "testid", email: TEST_EMAIL }, "fallback-secret");

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

describe("POST /api/payments", () => {
  it("should return 401 when no token provided", async () => {
    const res = await request(app).post("/api/payments").send({ orderId: "order123", amount: 500 });

    expect(res.status).toBe(401);
  });

  it("should return 401 for invalid token", async () => {
    const res = await request(app)
      .post("/api/payments")
      .set("Authorization", "Bearer invalidtoken.bad.signature")
      .send({ orderId: "order123", amount: 500 });

    expect(res.status).toBe(401);
    expect(res.body.error).toBe("Invalid or expired token.");
  });

  it("should return 500 when database throws on save", async () => {
    const Payment = require("../src/models/payment.model");
    const saveSpy = jest
      .spyOn(Payment.prototype, "save")
      .mockRejectedValueOnce(new Error("DB error"));

    const res = await request(app)
      .post("/api/payments")
      .set("Authorization", `Bearer ${validToken}`)
      .send({ orderId: "order123", amount: 500 });

    expect(res.status).toBe(500);
    expect(res.body.error).toBe("Server error");
    saveSpy.mockRestore();
  });

  it("should process payment successfully", async () => {
    const res = await request(app)
      .post("/api/payments")
      .set("Authorization", `Bearer ${validToken}`)
      .send({ orderId: "order123", amount: 500 });

    expect(res.status).toBe(200);
    expect(res.body.message).toBe("Payment successful");
    expect(res.body.status).toBe("paid");
    expect(res.body.orderId).toBe("order123");
    expect(res.body.amount).toBe(500);
    expect(res.body.paidAt).toBeDefined();
  });

  it("should return 422 when orderId is missing", async () => {
    const res = await request(app)
      .post("/api/payments")
      .set("Authorization", `Bearer ${validToken}`)
      .send({ amount: 500 });

    expect(res.status).toBe(422);
    expect(res.body.errors).toBeDefined();
  });

  it("should return 422 when amount is missing", async () => {
    const res = await request(app)
      .post("/api/payments")
      .set("Authorization", `Bearer ${validToken}`)
      .send({ orderId: "order123" });

    expect(res.status).toBe(422);
    expect(res.body.errors).toBeDefined();
  });

  it("should return 422 when both fields are missing", async () => {
    const res = await request(app)
      .post("/api/payments")
      .set("Authorization", `Bearer ${validToken}`)
      .send({});

    expect(res.status).toBe(422);
    expect(res.body.errors).toBeDefined();
  });
});

describe("GET /api/payments", () => {
  it("should return payment list", async () => {
    const res = await request(app).get("/api/payments");

    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
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
