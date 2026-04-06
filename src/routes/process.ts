import { Hono } from "hono";
import { join, extname, basename } from "node:path";
import { config, MAX_FILE_SIZE_BYTES } from "../config";
import { logger } from "../logger";
import { sanitizeArguments, runFfmpeg } from "../ffmpeg";
import { cleanStaleFiles, deleteFile } from "../cleanup";

export const processRouter = new Hono();

processRouter.post("/process", async (c) => {
  const requestStart = Date.now();

  // Clean stale files before every request
  await cleanStaleFiles();

  const contentType = c.req.header("content-type") ?? "";

  let file: File | null = null;
  let url: string | null = null;
  let rawArguments = "";
  let outputFilename: string | undefined;

  if (contentType.includes("multipart/form-data")) {
    const formData = await c.req.formData();
    const uploadedFile = formData.get("file");
    url = formData.get("url") as string | null;
    rawArguments = (formData.get("arguments") as string) ?? "";
    outputFilename =
      (formData.get("output_filename") as string) || undefined;

    if (uploadedFile instanceof File) {
      file = uploadedFile;
    }
  } else if (contentType.includes("application/json")) {
    const body = await c.req.json();
    url = body.url ?? null;
    rawArguments = body.arguments ?? "";
    outputFilename = body.output_filename || undefined;
  } else {
    return c.json(
      { error: "Unsupported Content-Type. Use multipart/form-data or application/json (for URL mode)." },
      400,
    );
  }

  // Validate: must have exactly one of file or url
  if (file && url) {
    return c.json(
      { error: "Provide either a file or a url, not both." },
      400,
    );
  }
  if (!file && !url) {
    return c.json(
      { error: "Provide either a file upload or a url to process." },
      400,
    );
  }

  if (!rawArguments.trim()) {
    return c.json(
      { error: "The 'arguments' field is required (ffmpeg processing arguments)." },
      400,
    );
  }

  // Determine input file path
  let inputPath: string;
  let originalName: string;

  if (file) {
    if (file.size > MAX_FILE_SIZE_BYTES) {
      return c.json(
        {
          error: `File too large. Maximum size is ${config.maxFileSizeMb}MB.`,
        },
        413,
      );
    }

    originalName = file.name || "input";
    const uniqueId = crypto.randomUUID();
    inputPath = join(config.uploadDir, `${uniqueId}_${originalName}`);

    await Bun.write(inputPath, file);
  } else {
    // Download from URL
    try {
      const parsedUrl = new URL(url!);
      originalName =
        basename(parsedUrl.pathname) || "input";

      logger.info({ url }, "Downloading file from URL");
      const response = await fetch(url!);

      if (!response.ok) {
        return c.json(
          { error: `Failed to download file from URL: ${response.status} ${response.statusText}` },
          400,
        );
      }

      const contentLength = parseInt(
        response.headers.get("content-length") ?? "0",
        10,
      );
      if (contentLength > MAX_FILE_SIZE_BYTES) {
        return c.json(
          {
            error: `Remote file too large. Maximum size is ${config.maxFileSizeMb}MB.`,
          },
          413,
        );
      }

      const uniqueId = crypto.randomUUID();
      inputPath = join(config.uploadDir, `${uniqueId}_${originalName}`);
      await Bun.write(inputPath, response);
    } catch (err) {
      return c.json(
        { error: `Invalid or unreachable URL: ${(err as Error).message}` },
        400,
      );
    }
  }

  // Build output filename
  const ext = extname(originalName);
  const base = basename(originalName, ext);
  const resolvedOutputName =
    outputFilename ?? `${base}_transformed${ext}`;
  const uniqueOutputId = crypto.randomUUID();
  const outputPath = join(
    config.uploadDir,
    `${uniqueOutputId}_${resolvedOutputName}`,
  );

  // Sanitize and run ffmpeg
  const args = sanitizeArguments(rawArguments);

  logger.info(
    {
      originalName,
      fileSize: file?.size ?? "url",
      arguments: rawArguments,
      sanitizedArgs: args,
    },
    "Processing request",
  );

  const result = await runFfmpeg(inputPath, outputPath, args);

  // Clean up input immediately
  await deleteFile(inputPath);

  if (!result.success) {
    await deleteFile(outputPath);
    return c.json(
      {
        error: "ffmpeg processing failed",
        details: result.stderr.slice(-2000),
        durationMs: result.durationMs,
      },
      422,
    );
  }

  // Read output and stream it back
  const outputFile = Bun.file(outputPath);
  const exists = await outputFile.exists();
  if (!exists) {
    return c.json(
      { error: "ffmpeg produced no output file" },
      500,
    );
  }

  const outputSize = outputFile.size;
  const outputBytes = await outputFile.arrayBuffer();

  // Delete output file immediately
  await deleteFile(outputPath);

  const totalDurationMs = Date.now() - requestStart;

  logger.info(
    {
      originalName,
      outputName: resolvedOutputName,
      inputSize: file?.size ?? "url",
      outputSize,
      ffmpegDurationMs: result.durationMs,
      totalDurationMs,
    },
    "Request completed successfully",
  );

  return new Response(outputBytes, {
    status: 200,
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Disposition": `attachment; filename="${resolvedOutputName}"`,
      "Content-Length": String(outputSize),
      "X-Processing-Duration-Ms": String(result.durationMs),
      "X-Total-Duration-Ms": String(totalDurationMs),
    },
  });
});
