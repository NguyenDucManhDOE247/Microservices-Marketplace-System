const request = require("supertest");
const mongoose = require("mongoose");
const { MongoMemoryServer } = require("mongodb-memory-server");

let mongoServer;

beforeAll(async () => {
  mongoServer = await MongoMemoryServer.create();
  await mongoose.connect(mongoServer.getUri());
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

// Lazy-load app after mongoose is connected to avoid connection race
let app;
beforeAll(() => {
  app = require("../src/app");
});

describe("POST /api/users/register", () => {
  it("should register a new user successfully", async () => {
    const res = await request(app)
      .post("/api/users/register")
      .send({ email: "test@example.com", password: "password123" });

    expect(res.status).toBe(200);
    expect(res.body.message).toBe("Registration successful");
  });

  it("should return 422 for invalid email format", async () => {
    const res = await request(app)
      .post("/api/users/register")
      .send({ email: "notanemail", password: "password123" });

    expect(res.status).toBe(422);
    expect(res.body.errors).toBeDefined();
  });

  it("should return 422 for password shorter than 6 characters", async () => {
    const res = await request(app)
      .post("/api/users/register")
      .send({ email: "valid@example.com", password: "123" });

    expect(res.status).toBe(422);
    expect(res.body.errors).toBeDefined();
  });

  it("should return 400 if email already exists", async () => {
    await request(app)
      .post("/api/users/register")
      .send({ email: "dup@example.com", password: "password123" });

    const res = await request(app)
      .post("/api/users/register")
      .send({ email: "dup@example.com", password: "password456" });

    expect(res.status).toBe(400);
    expect(res.body.error).toBe("Email already exists");
  });
});

describe("POST /api/users/login", () => {
  beforeEach(async () => {
    await request(app)
      .post("/api/users/register")
      .send({ email: "login@example.com", password: "secret123" });
  });

  it("should return 422 for invalid email format on login", async () => {
    const res = await request(app)
      .post("/api/users/login")
      .send({ email: "bademail", password: "secret123" });

    expect(res.status).toBe(422);
    expect(res.body.errors).toBeDefined();
  });

  it("should login successfully and return a token", async () => {
    const res = await request(app)
      .post("/api/users/login")
      .send({ email: "login@example.com", password: "secret123" });

    expect(res.status).toBe(200);
    expect(res.body.message).toBe("Login successful");
    expect(res.body.token).toBeDefined();
  });

  it("should return 401 with wrong password", async () => {
    const res = await request(app)
      .post("/api/users/login")
      .send({ email: "login@example.com", password: "wrongpass" });

    expect(res.status).toBe(401);
    expect(res.body.error).toBe("Incorrect password");
  });

  it("should return 400 if user not found", async () => {
    const res = await request(app)
      .post("/api/users/login")
      .send({ email: "nobody@example.com", password: "pass" });

    expect(res.status).toBe(400);
    expect(res.body.error).toBe("User not found");
  });
});

describe("GET /api/users/check/:email", () => {
  beforeEach(async () => {
    await request(app)
      .post("/api/users/register")
      .send({ email: "exist@example.com", password: "pass123" });
  });

  it("should return exists:true for registered email", async () => {
    const res = await request(app).get("/api/users/check/exist@example.com");

    expect(res.status).toBe(200);
    expect(res.body.exists).toBe(true);
  });

  it("should return 404 for unregistered email", async () => {
    const res = await request(app).get("/api/users/check/ghost@example.com");

    expect(res.status).toBe(404);
    expect(res.body.exists).toBe(false);
  });
});

describe("GET /api/users/", () => {
  it("should return demo user list", async () => {
    const res = await request(app).get("/api/users/");

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

describe("POST /api/users/register - server error", () => {
  it("should return 500 when database throws on save", async () => {
    const User = require("../src/models/user.model");
    const saveSpy = jest.spyOn(User.prototype, "save").mockRejectedValueOnce(new Error("DB error"));

    const res = await request(app)
      .post("/api/users/register")
      .send({ email: "error@example.com", password: "password123" });

    expect(res.status).toBe(500);
    expect(res.body.error).toBe("Server error");
    saveSpy.mockRestore();
  });
});

describe("POST /api/users/login - server error", () => {
  it("should return 500 when database throws on findOne", async () => {
    const User = require("../src/models/user.model");
    const findSpy = jest.spyOn(User, "findOne").mockRejectedValueOnce(new Error("DB error"));

    const res = await request(app)
      .post("/api/users/login")
      .send({ email: "login@example.com", password: "secret123" });

    expect(res.status).toBe(500);
    expect(res.body.error).toBe("Server error");
    findSpy.mockRestore();
  });
});
