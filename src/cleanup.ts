import { readdir, unlink, stat } from "node:fs/promises";
import { join } from "node:path";
import { config } from "./config";
import { logger } from "./logger";

const STALE_THRESHOLD_MS = 10 * 60 * 1000; // 10 minutes

export async function ensureUploadDir() {
  const { mkdirSync } = await import("node:fs");
  mkdirSync(config.uploadDir, { recursive: true });
}

export async function cleanStaleFiles() {
  try {
    const entries = await readdir(config.uploadDir);
    const now = Date.now();
    let removed = 0;

    for (const entry of entries) {
      const filePath = join(config.uploadDir, entry);
      try {
        const s = await stat(filePath);
        if (now - s.mtimeMs > STALE_THRESHOLD_MS) {
          await unlink(filePath);
          removed++;
        }
      } catch {
        // file may have been deleted by another request
      }
    }

    if (removed > 0) {
      logger.info({ removed }, "Cleaned stale files");
    }
  } catch {
    // directory may not exist yet
  }
}

export async function deleteFile(path: string) {
  try {
    await unlink(path);
  } catch {
    // already deleted
  }
}
