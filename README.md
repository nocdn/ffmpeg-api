# ffmpeg-api-container

A lightweight REST API for processing media files with ffmpeg. Runs in Docker with Bun + Hono.

## Deploying

```bash
cp .env.example .env   # adjust values as needed
docker compose up -d
```

The API will be available at `http://localhost:8040` (or whatever `PORT` you set).

## Endpoints

### `GET /api/health`

Returns service status, ffmpeg version, uptime, and system info.

```bash
curl http://localhost:8040/api/health
```

```json
{
  "status": "ok",
  "uptime": "120s",
  "ffmpeg": "ffmpeg version 6.1.2 ...",
  "memory": { "rss": "53MB", "heapUsed": "2MB" },
  "system": { "platform": "linux", "arch": "arm64", "cpus": 8, "freeMemory": "7244MB" }
}
```

### `POST /api/process`

Process a media file with ffmpeg arguments. Accepts either a direct file upload or a URL. Returns the processed file as a binary download.

**Parameters:**

| Field             | Type   | Required | Description                                                                 |
| ----------------- | ------ | -------- | --------------------------------------------------------------------------- |
| `file`            | file   | *        | File upload (multipart). Mutually exclusive with `url`.                     |
| `url`             | string | *        | URL to download the file from. Mutually exclusive with `file`.              |
| `arguments`       | string | ✓        | ffmpeg arguments (e.g. `-vf scale=640:-1 -c:a copy`).                      |
| `output_filename` | string |          | Custom output filename. Defaults to `<original>_transformed.<ext>`.        |

> `ffmpeg` and `-i <input>` prefixes are automatically stripped if included in `arguments`.

**File upload (multipart):**

```bash
curl -o output.mp4 \
  -F "file=@input.mp4" \
  -F "arguments=-vf scale=640:-1 -c:a copy" \
  http://localhost:8040/api/process
```

**URL mode (JSON):**

```bash
curl -o output.mp4 \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.mp4", "arguments": "-vf scale=640:-1"}' \
  http://localhost:8040/api/process
```

**Custom output filename:**

```bash
curl -o result.mp4 \
  -F "file=@input.mp4" \
  -F "arguments=-vf scale=640:-1" \
  -F "output_filename=small.mp4" \
  http://localhost:8040/api/process
```

**Response headers** include `X-Processing-Duration-Ms` and `X-Total-Duration-Ms` for timing info.

## Environment Variables

| Variable                     | Default | Description                                           |
| ---------------------------- | ------- | ----------------------------------------------------- |
| `PORT`                       | `8040`  | Server port                                           |
| `MAX_FILE_SIZE_MB`           | `2048`  | Maximum upload file size in MB                        |
| `RATE_LIMIT_PER_MINUTE`      | `1`     | Global rate limit for `/api/process` (reqs/min)       |
| `HEALTH_RATE_LIMIT_PER_MINUTE` | `60`  | Rate limit for `/api/health` (reqs/min)               |
| `PROCESS_TIMEOUT_SECONDS`    | `360`   | Max ffmpeg execution time before the process is killed |

## Error Responses

All errors return JSON:

```json
{ "error": "description of what went wrong" }
```

| Status | Meaning                          |
| ------ | -------------------------------- |
| `400`  | Bad request (missing/invalid input) |
| `413`  | File exceeds `MAX_FILE_SIZE_MB`  |
| `422`  | ffmpeg processing failed         |
| `429`  | Rate limit exceeded              |
