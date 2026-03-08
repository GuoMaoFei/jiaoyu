FROM python:3.10-slim
WORKDIR /app

# System dependencies for SQLite and async operations
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy codebase
COPY . .

# Set permissions and python path
ENV PYTHONPATH=/app
EXPOSE 8000

# Start Uvicorn async production server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
