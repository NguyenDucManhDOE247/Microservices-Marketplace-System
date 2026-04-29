const request = require("supertest");
const app = require("../src/app");

describe("POST /api/payments", () => {
  it("should process payment successfully", async () => {
    const res = await request(app)
      .post("/api/payments")
      .send({ orderId: "order123", amount: 500 });

    expect(res.status).toBe(200);
    expect(res.body.message).toBe("Payment successful");
    expect(res.body.status).toBe("paid");
    expect(res.body.orderId).toBe("order123");
    expect(res.body.amount).toBe(500);
    expect(res.body.paidAt).toBeDefined();
  });

  it("should return 400 when orderId is missing", async () => {
    const res = await request(app)
      .post("/api/payments")
      .send({ amount: 500 });

    expect(res.status).toBe(400);
    expect(res.body.error).toBe("Missing orderId or amount");
  });

  it("should return 400 when amount is missing", async () => {
    const res = await request(app)
      .post("/api/payments")
      .send({ orderId: "order123" });

    expect(res.status).toBe(400);
    expect(res.body.error).toBe("Missing orderId or amount");
  });

  it("should return 400 when both fields are missing", async () => {
    const res = await request(app)
      .post("/api/payments")
      .send({});

    expect(res.status).toBe(400);
  });
});

describe("GET /api/payments", () => {
  it("should return payment list", async () => {
    const res = await request(app).get("/api/payments");

    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
  });
});
