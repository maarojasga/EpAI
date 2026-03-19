# Use an official lightweight Python image.
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Set destination for COPY
WORKDIR /app

# Install system dependencies (needed for llama-cpp, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port Cloud Run expects
EXPOSE 8080

# Run the web service using uvicorn.
# Cloud Run sets the PORT env var automatically.
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
