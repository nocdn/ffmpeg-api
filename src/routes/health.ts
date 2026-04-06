import { Hono } from "hono";
import os from "node:os";

const startedAt = Date.now();

async function getFfmpegVersion(): Promise<string> {
  try {
    const proc = Bun.spawn(["ffmpeg", "-version"], {
      stdout: "pipe",
      stderr: "pipe",
    });
    const text = await new Response(proc.stdout).text();
    return text.split("\n")[0] ?? "unknown";
  } catch {
    return "not available";
  }
}

export const healthRouter = new Hono();

healthRouter.get("/health", async (c) => {
  const uptimeMs = Date.now() - startedAt;
  const uptimeSeconds = Math.floor(uptimeMs / 1000);
  const mem = process.memoryUsage();

  return c.json({
    status: "ok",
    uptime: `${uptimeSeconds}s`,
    ffmpeg: await getFfmpegVersion(),
    memory: {
      rss: `${Math.round(mem.rss / 1024 / 1024)}MB`,
      heapUsed: `${Math.round(mem.heapUsed / 1024 / 1024)}MB`,
    },
    system: {
      platform: os.platform(),
      arch: os.arch(),
      cpus: os.cpus().length,
      freeMemory: `${Math.round(os.freemem() / 1024 / 1024)}MB`,
    },
  });
});
