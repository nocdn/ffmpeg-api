import os
import subprocess
import uuid
import shutil
import shlex # For safely splitting command strings
import mimetypes
from pathlib import Path
# Remove TemporaryDirectory import if no longer needed elsewhere
# from tempfile import TemporaryDirectory
import tempfile # Import the base module

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

# --- Configuration ---
FFMPEG_PATH = "ffmpeg"

app = FastAPI(title="FFmpeg API")

# (FFmpeg check code remains the same)
print("Checking for ffmpeg...")
try:
    result = subprocess.run([FFMPEG_PATH, "-version"], capture_output=True, text=True, check=True)
    print("FFmpeg found:")
    print(result.stdout.splitlines()[0])
except (FileNotFoundError, subprocess.CalledProcessError) as e:
    print(f"Error: ffmpeg command not found or failed to execute at '{FFMPEG_PATH}'. Please ensure FFmpeg is installed and in the system's PATH.")
    print(f"Details: {e}")

def cleanup_temp_dir(temp_dir_path: str):
    """Safely remove the temporary directory."""
    try:
        if os.path.exists(temp_dir_path):
            print(f"Attempting to clean up temporary directory: {temp_dir_path}")
            shutil.rmtree(temp_dir_path)
            print(f"Successfully cleaned up temporary directory: {temp_dir_path}")
        else:
            print(f"Temporary directory already removed or never existed: {temp_dir_path}")
    except Exception as e:
        print(f"Error cleaning up temp dir {temp_dir_path}: {e}")

def generate_output_filename(input_filename: str, requested_filename: str | None = None) -> str:
    """Generates the output filename based on input or request."""
    if requested_filename:
        sanitized_name = "".join(c if c.isalnum() or c in ['.', '_', '-'] else '_' for c in requested_filename)
        if not sanitized_name:
             raise ValueError("Requested output filename is invalid after sanitization.")
        return sanitized_name

    base, ext = os.path.splitext(input_filename)
    if not base and ext:
         base = ext
         ext = ""
    elif '.' not in input_filename:
         base = input_filename
         ext = ""

    return f"{base}_transformed{ext}"


@app.post("/process", response_class=FileResponse)
async def process_file_with_ffmpeg(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="The input media file."),
    commands: str = Form(..., description="FFmpeg command arguments (e.g., '-vf scale=640:-1 -c:a copy'). Do not include 'ffmpeg -i input.mp4 ... output.mp4'."),
    output_filename: str | None = Form(None, description="Optional desired output filename. If not provided, '_transformed' will be appended to the input name.")
):
    """
    Applies FFmpeg commands to the uploaded file and returns the result.
    (Docstring remains the same)
    """

    temp_dir_path = None # Initialize to None
    try:
        # --- 1. Create Temporary Directory using mkdtemp ---
        # mkdtemp creates the directory and returns the path, without automatic cleanup object
        temp_dir_path = tempfile.mkdtemp(prefix="ffmpeg_api_")
        print(f"Created temporary directory: {temp_dir_path}")

        # Add cleanup task *before* potential errors, relying solely on BackgroundTasks
        background_tasks.add_task(cleanup_temp_dir, temp_dir_path)


        # --- 2. Save Uploaded File ---
        input_filename_orig = file.filename or "input_file"
        safe_input_basename = "".join(c if c.isalnum() or c in ['.', '_', '-'] else '_' for c in input_filename_orig)
        if not safe_input_basename: safe_input_basename = f"input_{uuid.uuid4().hex}"
        input_file_path = os.path.join(temp_dir_path, safe_input_basename)

        try:
            with open(input_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            print(f"Saved uploaded file to: {input_file_path}")
        except Exception as e:
            print(f"Error saving uploaded file: {e}")
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not save uploaded file: {e}",
            )
        finally:
            await file.close()


        # --- 3. Determine Output Filename & Path ---
        try:
            final_output_filename = generate_output_filename(input_filename_orig, output_filename)
        except ValueError as e:
             raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))

        output_file_path = os.path.join(temp_dir_path, final_output_filename)
        print(f"Target output file path: {output_file_path}")


        # --- 4. Construct and Run FFmpeg Command ---
        try:
            if not commands or commands.isspace():
                 raise ValueError("FFmpeg commands cannot be empty.")
            command_args = shlex.split(commands)
        except ValueError as e:
             print(f"Error splitting command string: '{commands}'. Error: {e}")
             raise HTTPException(
                 status_code=HTTP_400_BAD_REQUEST,
                 detail=f"Invalid command string format: {e}. Ensure proper quoting if needed."
             )

        ffmpeg_command = [
            FFMPEG_PATH,
            "-i", input_file_path,
            *command_args,
            output_file_path
        ]

        print(f"Running FFmpeg command: {' '.join(shlex.quote(str(arg)) for arg in ffmpeg_command)}")

        try:
            process = subprocess.run(
                ffmpeg_command,
                capture_output=True,
                text=True,
                check=True
            )
            # Optional: Log less verbosely on success
            # print("FFmpeg stdout (truncated):", process.stdout[:200])
            # print("FFmpeg stderr (truncated):", process.stderr[:500]) # Stderr often has more info
            print(f"FFmpeg processing successful. Output file: {output_file_path}")

        except subprocess.CalledProcessError as e:
            print(f"FFmpeg execution failed with exit code {e.returncode}")
            print("FFmpeg stdout:")
            print(e.stdout)
            print("FFmpeg stderr:")
            print(e.stderr)
            error_detail = f"FFmpeg error (code {e.returncode}): {e.stderr or e.stdout or 'No output captured.'}"
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail
            )
        except FileNotFoundError:
             print(f"Error: The '{FFMPEG_PATH}' command was not found.")
             raise HTTPException(
                  status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                  detail=f"FFmpeg command not found on the server. Path used: '{FFMPEG_PATH}'"
             )
        except Exception as e:
            print(f"An unexpected error occurred during FFmpeg execution: {e}")
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {e}"
            )


        # --- 5. Return the Resulting File ---
        if not os.path.exists(output_file_path):
            print(f"Error: Output file '{output_file_path}' not found after FFmpeg command completion (race condition likely avoided, check ffmpeg logs again).")
            # If this error *still* happens, FFmpeg might be failing silently despite check=True,
            # or there's a deeper filesystem/permission issue.
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail="FFmpeg seemed to complete, but the output file was not found. Check API logs and FFmpeg command."
            )

        media_type, _ = mimetypes.guess_type(output_file_path)
        media_type = media_type or 'application/octet-stream'

        # Now FileResponse should work because the directory is not deleted prematurely
        return FileResponse(
            path=output_file_path,
            filename=final_output_filename,
            media_type=media_type,
            # background=cleanup_task # No longer needed here, BackgroundTasks handles it
        )
    except Exception as e:
        # Catch any other unexpected errors during setup/processing
        print(f"Unhandled exception in /process endpoint: {e}")
        # Ensure cleanup task is still added if temp dir was created before the error
        if temp_dir_path and os.path.exists(temp_dir_path):
             print(f"Adding cleanup task for {temp_dir_path} due to error.")
             # Be careful not to add the task twice if it was already added in the main flow
             # Using a flag or checking if the task exists might be needed for robustness,
             # but BackgroundTasks might handle duplicates gracefully. For simplicity:
             # background_tasks.add_task(cleanup_temp_dir, temp_dir_path) # Potentially adds twice, check behavior
             pass # Rely on the initial add_task from the try block

        raise HTTPException(
             status_code=HTTP_500_INTERNAL_SERVER_ERROR,
             detail=f"An internal server error occurred: {str(e)}"
         )

# (Root endpoint remains the same)
@app.get("/")
async def root():
    return {"message": "FFmpeg API is running. Use the /process endpoint to transform files."}