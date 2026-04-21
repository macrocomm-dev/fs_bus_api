FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install OS-level dependencies needed by psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/

# Expose the port uvicorn listens on
EXPOSE 8080

# Run the API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
