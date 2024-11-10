from flask import Flask, request, send_file, jsonify
import os
import subprocess
from werkzeug.utils import secure_filename
import shlex
import uuid
from functools import wraps
import shutil
import logging
from datetime import datetime
import time

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = app.logger
file_handler = logging.FileHandler('app.log')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(request_id)s] - %(message)s'
))
logger.addHandler(file_handler)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    logger.info(f"Created upload folder: {UPLOAD_FOLDER}")

def get_request_id():
    return str(uuid.uuid4())[:8]

def log_context(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        request_id = get_request_id()
        # Add request_id to logging context
        context = {'request_id': request_id}
        logger.info(f"New request started", extra=context)
        start_time = time.time()
        
        try:
            return func(*args, **kwargs, request_id=request_id)
        finally:
            duration = time.time() - start_time
            logger.info(f"Request completed in {duration:.2f}s", extra=context)
    return wrapper

def cleanup_files(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        temp_files = []
        request_id = kwargs.get('request_id', 'unknown')
        context = {'request_id': request_id}
        
        try:
            result = func(*args, **kwargs, temp_files=temp_files)
            return result
        finally:
            # Clean up any temporary files
            for file_path in temp_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Cleaned up temporary file: {file_path}", extra=context)
                except Exception as e:
                    logger.error(f"Error cleaning up {file_path}: {e}", extra=context)
    return wrapper

@app.route('/process', methods=['POST'])
@log_context
@cleanup_files
def process_video(temp_files=None, request_id=None):
    context = {'request_id': request_id}
    
    logger.info("Processing new video request", extra=context)
    
    if 'file' not in request.files:
        logger.error("No file provided in request", extra=context)
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.error("Empty filename provided", extra=context)
        return jsonify({'error': 'No file selected'}), 400

    # Get FFmpeg flags from request
    ffmpeg_flags = request.form.get('flags')
    if not ffmpeg_flags:
        logger.error("No FFmpeg flags provided", extra=context)
        return jsonify({'error': 'No FFmpeg flags provided'}), 400

    # Get output filename from request
    output_filename = request.form.get('output_filename')
    if not output_filename:
        logger.error("No output filename provided", extra=context)
        return jsonify({'error': 'No output filename provided'}), 400

    try:
        # Generate unique filenames
        input_filename = secure_filename(str(uuid.uuid4()) + '_' + file.filename)
        temp_output_filename = secure_filename(str(uuid.uuid4()) + '_' + output_filename)

        input_path = os.path.join(UPLOAD_FOLDER, input_filename)
        output_path = os.path.join(UPLOAD_FOLDER, temp_output_filename)

        logger.info(f"Generated temporary paths - Input: {input_path}, Output: {output_path}", extra=context)

        # Add files to cleanup list
        temp_files.extend([input_path, output_path])

        # Save uploaded file
        file.save(input_path)
        logger.info(f"Saved uploaded file to {input_path}", extra=context)

        # Construct FFmpeg command
        base_command = f'ffmpeg -i "{input_path}" {ffmpeg_flags} "{output_path}"'
        command = shlex.split(base_command)
        logger.info(f"Executing FFmpeg command: {base_command}", extra=context)

        # Run FFmpeg command
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if process.returncode != 0:
            logger.error(f"FFmpeg processing failed: {process.stderr}", extra=context)
            return jsonify({
                'error': 'FFmpeg processing failed',
                'details': process.stderr
            }), 500

        logger.info("FFmpeg processing completed successfully", extra=context)
        
        # Return processed file
        logger.info(f"Sending processed file: {output_filename}", extra=context)
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename
        )

    except Exception as e:
        logger.exception(f"Unexpected error during processing: {str(e)}", extra=context)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting Flask application on port 7005")
    app.run(host='0.0.0.0', port=7005)