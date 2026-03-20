# Use official Python lightweight image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CATALOG_PATH=data/IID-SID-ITEM.csv

# Set work directory
WORKDIR /app

# Install system dependencies for psycopg2 and other tools
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create data directory for local persistence if needed
RUN mkdir -p data

# Expose the API port
EXPOSE 8002

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
