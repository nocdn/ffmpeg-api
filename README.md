# ffmpeg-api

> self-hosted REST API built with FastAPI to expose FFmpeg functionality for processing media files.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This API provides a simple `/process` endpoint that accepts a media file upload and FFmpeg command arguments. It executes FFmpeg with the provided commands on the server and returns the resulting processed file.

### Deployment with Docker (Recommended)

##### Prerequisites

- [Docker](https://www.docker.com/) installed.
- FFmpeg is installed _within_ the Docker image, so you **don't need it** installed locally on the host machine when using Docker.

##### Setup Steps

1.  **Clone the repository** and navigate into the directory:

    ```bash
    git clone https://github.com/nocdn/ffmpeg-api.git
    cd ffmpeg-api/
    ```

2.  **Build the Docker Image**:
    This command builds the image using the provided `Dockerfile`.

    ```bash
    docker build -t ffmpeg-api-img .
    ```

3.  **Run the Docker Container**:
    This command runs the container in detached mode (`-d`), maps the host's port 8040 to the container's port 8080 (where the API runs, you can change this port to whatever you want), and names the container `ffmpeg-api-container`. The `--restart=always` flag ensures the container restarts automatically if it stops.

    ```bash
    docker run -d \
      --restart=always \
      -p 8040:8080 \
      --name ffmpeg-api-container \
      ffmpeg-api-img
    ```

The API should now be running and accessible at `http://<your_server_ip>:8040` or `http://localhost:8040` if running locally.

### Usage

The API provides the following endpoints:

**Process a media file:**

Submit a `POST` request to the `/process` endpoint with multipart/form-data containing:

- `file`: The media file to be processed.
- `commands`: A string containing the FFmpeg arguments to apply (e.g., `-vf scale=640:-1 -c:a copy`). **Important:** Do _not_ include `ffmpeg`, `-i input_file`, or the output filename in this string; only provide the options/arguments that go between the input and output specifications.
- `output_filename` (Optional): A desired filename for the output file. If not provided, `_transformed` will be appended to the original filename (before the extension).

Example using `curl`:

```bash
# Example: Scale video width to 640px, keep aspect ratio, copy audio stream
# Replace 'input.mp4' with your actual file path
# Replace 'localhost:8040' with your API's address if needed
# The output will be saved to 'output.mp4' in your current directory

curl -X POST http://localhost:8040/process \
  -F "file=@input.mp4" \
  -F "commands=-vf scale=640:-1 -c:a copy" \
  -o output.mp4
```

Example specifying an output filename:

```bash
curl -X POST http://localhost:8040/process \
  -F "file=@input.mov" \
  -F "commands=-c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k" \
  -F "output_filename=converted_video.mp4" \
  -o converted_video.mp4
```

_Successful Response (200 OK):_

- The API returns the processed file directly. The `curl -o <filename>` command saves this response body to a local file.
- The `Content-Disposition` header will suggest the original or requested output filename.
- The `Content-Type` header will be set based on the output file's extension (e.g., `video/mp4`, `audio/mpeg`).

_Error Responses:_

- `400 Bad Request`: If the `commands` string is missing, empty, or invalidly formatted.
- `422 Unprocessable Entity`: If required form fields (`file`, `commands`) are missing.
- `500 Internal Server Error`: If FFmpeg fails during execution (details usually included in the response body), if the output file isn't created, or if another server-side error occurs. The API logs will contain more detailed FFmpeg output (stdout/stderr) in case of errors.

**Health Check:**

```bash
curl http://localhost:8040/
```

_Response (200 OK):_

```json
{
  "message": "FFmpeg API is running. Use the /process endpoint to transform files."
}
```

### Installation for Local Development

##### Prerequisites

- Python 3.8+ (check your specific FastAPI/Uvicorn compatibility needs, 3.10+ recommended)
- `pip` and `venv`
- **FFmpeg**: You _must_ have the `ffmpeg` command-line tool installed and accessible in your system's PATH. You can download it from [ffmpeg.org](https://ffmpeg.org/download.html) or install via a package manager (e.g., `apt install ffmpeg`, `brew install ffmpeg`).

> [!IMPORTANT]
> Unlike the Docker setup, for local development, **FFmpeg must be installed directly on your machine** for the Python code to call it. Verify the installation by running `ffmpeg -version` in your terminal.

##### Setup Steps

1.  **Clone the repository**:

    ```bash
    git clone https://github.com/nocdn/ffmpeg-api.git
    cd ffmpeg-api/
    ```

2.  **Create Virtual Environment & Install Dependencies**:

    ```bash
    python3 -m venv venv
    source venv/bin/activate  # on Windows use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Run the API**:
    This command starts the Uvicorn server.

    ```bash
    # Navigate to the directory containing the 'app' folder if you aren't already
    # cd /path/to/ffmpeg-api/
    uvicorn app.main:app --host 0.0.0.0 --port 8040
    ```

    _(For development, you might want to add `--reload`)_

The API will run directly on your machine, accessible at `http://localhost:8040`. Temporary files generated during processing will be created in your system's default temporary directory and cleaned up afterward.

### License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
