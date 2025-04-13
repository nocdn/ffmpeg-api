# Use Debian testing slim as a parent image
FROM debian:testing-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Set work directory
WORKDIR /app

# Install system dependencies including Python 3, pip, venv, ffmpeg, and git
# - python3: Python interpreter
# - python3-pip: Python package installer
# - python3-venv: Virtual environment support
# - ffmpeg: the core tool
# - git: useful for some pip installs
# Clean up apt cache to reduce image size
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv ffmpeg git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python3 -m venv /opt/venv

# Install Python dependencies within the virtual environment
# Copy only requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY ./app /app/app

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application using Uvicorn from the virtual environment
# Use 0.0.0.0 to allow connections from outside the container
# Add --reload for development ONLY, remove for production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
# Development command: CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]