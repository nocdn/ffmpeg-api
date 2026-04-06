import { config } from "./config";
import { logger } from "./logger";

const BLOCKED_ARGS = [
  "-y",
  "-n",
  "-stdin",
  "-nostdin",
  "-filter_complex_script",
  "-lavfi",
];

const BLOCKED_ARGS_WITH_VALUES = new Set([
  "-filter_complex_script",
  "-lavfi",
]);

const VALUE_OPTIONS = new Set([
  "-analyzeduration",
  "-ar",
  "-aspect",
  "-async",
  "-b:a",
  "-b:v",
  "-b",
  "-bufsize",
  "-c:a",
  "-c:v",
  "-c",
  "-codec:a",
  "-codec:v",
  "-codec",
  "-crf",
  "-filter:a",
  "-filter:v",
  "-filter",
  "-f",
  "-frames:a",
  "-frames:v",
  "-frames",
  "-level",
  "-map",
  "-map_chapters",
  "-map_metadata",
  "-maxrate",
  "-metadata",
  "-minrate",
  "-movflags",
  "-pix_fmt",
  "-preset",
  "-profile:a",
  "-profile:v",
  "-profile",
  "-q:a",
  "-q:v",
  "-q",
  "-r",
  "-s",
  "-ss",
  "-t",
  "-threads",
  "-to",
  "-vf",
  "-filter_complex",
]);

function optionTakesValue(token: string): boolean {
  if (VALUE_OPTIONS.has(token)) {
    return true;
  }

  return [
    /^-b:[^:]+$/,
    /^-bsf(?::.+)?$/,
    /^-c:[^:]+$/,
    /^-codec:[^:]+$/,
    /^-disposition(?::.+)?$/,
    /^-filter:[^:]+$/,
    /^-map_metadata(?::.+)?$/,
    /^-metadata(?::.+)?$/,
    /^-profile:[^:]+$/,
    /^-q:[^:]+$/,
  ].some((pattern) => pattern.test(token));
}

export function sanitizeArguments(raw: string): string[] {
  let cleaned = raw.trim();

  // Strip leading "ffmpeg" invocation variants users commonly paste
  cleaned = cleaned.replace(/^ffmpeg\s+/i, "");
  cleaned = cleaned.replace(/^-i\s+\S+\s*/, "");

  // Tokenise respecting quoted strings
  const tokens: string[] = [];
  const regex = /(?:"([^"]*)")|(?:'([^']*)')|(\S+)/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(cleaned)) !== null) {
    tokens.push(match[1] ?? match[2] ?? match[3]);
  }

  // Filter dangerous / unnecessary tokens
  const filtered: string[] = [];
  let skipNextValue = false;

  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];

    if (skipNextValue) {
      skipNextValue = false;
      continue;
    }

    if (BLOCKED_ARGS.includes(t)) {
      logger.warn({ arg: t }, "Blocked ffmpeg argument stripped");
      if (BLOCKED_ARGS_WITH_VALUES.has(t)) {
        skipNextValue = true;
      }
      continue;
    }

    // Block -i (input) – we control the input
    if (t === "-i") {
      skipNextValue = true;
      continue;
    }

    if (!t.startsWith("-")) {
      logger.warn({ arg: t }, "Stripped positional ffmpeg output argument");
      continue;
    }

    filtered.push(t);

    if (optionTakesValue(t)) {
      const next = tokens[i + 1];
      if (next !== undefined) {
        filtered.push(next);
        i++;
      }
    }
  }

  return filtered;
}

export async function runFfmpeg(
  inputPath: string,
  outputPath: string,
  args: string[],
): Promise<{ success: boolean; stderr: string; durationMs: number }> {
  const start = Date.now();
  const cmd = ["ffmpeg", "-i", inputPath, ...args, "-y", outputPath];
  logger.info({ cmd: cmd.join(" ") }, "Running ffmpeg");

  const proc = Bun.spawn(cmd, {
    stdout: "pipe",
    stderr: "pipe",
  });

  const timeout = setTimeout(() => {
    logger.warn("ffmpeg process timed out, killing");
    proc.kill();
  }, config.processTimeoutSeconds * 1000);

  const exitCode = await proc.exited;
  clearTimeout(timeout);

  const stderr = await new Response(proc.stderr).text();
  const durationMs = Date.now() - start;

  if (exitCode !== 0) {
    logger.error({ exitCode, stderr }, "ffmpeg failed");
    return { success: false, stderr, durationMs };
  }

  return { success: true, stderr, durationMs };
}
