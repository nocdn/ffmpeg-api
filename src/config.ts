function envInt(key: string, fallback: number): number {
  const val = parseInt(process.env[key] ?? "", 10);
  return Number.isNaN(val) ? fallback : val;
}

export const config = {
  port: envInt("PORT", 8040),
  maxFileSizeMb: envInt("MAX_FILE_SIZE_MB", 2048),
  rateLimitPerMinute: envInt("RATE_LIMIT_PER_MINUTE", 1),
  healthRateLimitPerMinute: envInt("HEALTH_RATE_LIMIT_PER_MINUTE", 60),
  processTimeoutSeconds: envInt("PROCESS_TIMEOUT_SECONDS", 360),
  uploadDir: process.env.UPLOAD_DIR ?? "/tmp/ffmpeg-api",
} as const;

export const MAX_FILE_SIZE_BYTES = config.maxFileSizeMb * 1024 * 1024;
