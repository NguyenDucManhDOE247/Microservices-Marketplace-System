const express = require("express");
const cors = require("cors");
const promClient = require("prom-client");
const userRoutes = require("./routes/user.routes");

const app = express();

// ── Prometheus metrics setup ──────────────────────────────────────────────────
const register = new promClient.Registry();
register.setDefaultLabels({ app: "user-service" });
promClient.collectDefaultMetrics({ register, prefix: "osm_" });

const httpRequestsTotal = new promClient.Counter({
  name: "http_requests_total",
  help: "Total number of HTTP requests",
  labelNames: ["method", "route", "status_code"],
  registers: [register],
});

const httpRequestDuration = new promClient.Histogram({
  name: "http_request_duration_seconds",
  help: "HTTP request duration in seconds",
  labelNames: ["method", "route", "status_code"],
  buckets: [0.01, 0.05, 0.1, 0.3, 0.5, 1, 2, 5],
  registers: [register],
});
// ─────────────────────────────────────────────────────────────────────────────

app.use(cors());
app.use(express.json());

// Record metrics for every request
app.use((req, res, next) => {
  const start = Date.now();
  res.on("finish", () => {
    const duration = (Date.now() - start) / 1000;
    const route = req.route ? req.baseUrl + req.route.path : req.path;
    httpRequestsTotal.inc({ method: req.method, route, status_code: res.statusCode });
    httpRequestDuration.observe(
      { method: req.method, route, status_code: res.statusCode },
      duration,
    );
  });
  next();
});

// Expose Prometheus metrics
app.get("/metrics", async (req, res) => {
  res.set("Content-Type", register.contentType);
  res.end(await register.metrics());
});

app.use("/api/users", userRoutes);

// 404 fallback — also exercises the req.path branch in metrics middleware
app.use((req, res) => {
  res.status(404).json({ error: "Not found" });
});

module.exports = app;
