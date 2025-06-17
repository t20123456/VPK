FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install vastai CLI
RUN pip install vastai

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data/jobs /app/data/temp /app/data/uploads /app/logs

# Create non-root user for security
RUN useradd -m -u 1000 vpkuser && chown -R vpkuser:vpkuser /app
USER vpkuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Production command with multiple workers and database migration
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"]