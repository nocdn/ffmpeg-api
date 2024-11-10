from flask import Flask, request, send_file, jsonify
import os
import subprocess
from werkzeug.utils import secure_filename
import shlex
import uuid
from functools import wraps
import shutil

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def cleanup_files(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        temp_files = []
        try:
            result = func(*args, **kwargs, temp_files=temp_files)
            return result
        finally:
            # Clean up any temporary files
            for file_path in temp_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    app.logger.error(f"Error cleaning up {file_path}: {e}")
    return wrapper

@app.route('/process', methods=['POST'])
@cleanup_files
def process_video(temp_files=None):
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Get FFmpeg flags from request
    ffmpeg_flags = request.form.get('flags')
    if not ffmpeg_flags:
        return jsonify({'error': 'No FFmpeg flags provided'}), 400

    # Get output filename from request
    output_filename = request.form.get('output_filename')
    if not output_filename:
        return jsonify({'error': 'No output filename provided'}), 400

    try:
        # Generate unique filenames for temporary storage only
        input_filename = secure_filename(str(uuid.uuid4()) + '_' + file.filename)
        temp_output_filename = secure_filename(str(uuid.uuid4()) + '_' + output_filename)

        input_path = os.path.join(UPLOAD_FOLDER, input_filename)
        output_path = os.path.join(UPLOAD_FOLDER, temp_output_filename)

        # Add files to cleanup list
        temp_files.extend([input_path, output_path])

        # Save uploaded file
        file.save(input_path)

        # Construct FFmpeg command
        base_command = f'ffmpeg -i "{input_path}" {ffmpeg_flags} "{output_path}"'
        command = shlex.split(base_command)

        # Run FFmpeg command
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if process.returncode != 0:
            return jsonify({
                'error': 'FFmpeg processing failed',
                'details': process.stderr
            }), 500

        # Return processed file with original requested filename
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename  # Use original output filename here
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7005)
