FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.8.0

# Copy Poetry configuration
COPY pyproject.toml poetry.lock* /app/

# Configure Poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy application code
COPY . /app/

# Make scripts executable
RUN chmod +x /app/start.sh
RUN chmod +x /app/db/init-db.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV POSTGRES_PASSWORD=postgres

# Expose port
EXPOSE 8000

# Run the application with startup script
CMD ["/app/start.sh"]