import { Hono } from "hono";
import { rateLimiter } from "hono-rate-limiter";
import { config } from "./config";
import { logger } from "./logger";
import { ensureUploadDir, cleanStaleFiles } from "./cleanup";
import { healthRouter } from "./routes/health";
import { processRouter } from "./routes/process";

const app = new Hono();

// Health endpoint rate limiter (separate, more generous)
app.use(
  "/api/health",
  rateLimiter({
    windowMs: 60 * 1000,
    limit: config.healthRateLimitPerMinute,
    standardHeaders: "draft-6",
    keyGenerator: () => "global-health",
    message: { error: "Rate limit exceeded. Please try again later." },
  }),
);

// Process endpoint rate limiter
app.use(
  "/api/process",
  rateLimiter({
    windowMs: 60 * 1000,
    limit: config.rateLimitPerMinute,
    standardHeaders: "draft-6",
    keyGenerator: () => "global-process",
    message: { error: "Rate limit exceeded. Please try again later." },
  }),
);

// Request logging middleware
app.use("*", async (c, next) => {
  const start = Date.now();
  await next();
  const ms = Date.now() - start;
  logger.info(
    {
      method: c.req.method,
      path: c.req.path,
      status: c.res.status,
      durationMs: ms,
    },
    "Request handled",
  );
});

// Routes
app.route("/api", healthRouter);
app.route("/api", processRouter);

app.get("/", (c) =>
  c.json({
    name: "ffmpeg-api-container",
    status: "ok",
    endpoints: ["/api/health", "/api/process"],
  }),
);

// Startup
await ensureUploadDir();
await cleanStaleFiles();

const server = Bun.serve({
  fetch: app.fetch,
  port: config.port,
  maxRequestBodySize: 1024 * 1024 * config.maxFileSizeMb,
});

logger.info(
  {
    port: server.port,
    maxFileSizeMb: config.maxFileSizeMb,
    rateLimitPerMinute: config.rateLimitPerMinute,
    processTimeoutSeconds: config.processTimeoutSeconds,
  },
  `ffmpeg-api-container listening on http://localhost:${server.port}`,
);
