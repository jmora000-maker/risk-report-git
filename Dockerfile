FROM python:3.11-slim
WORKDIR /app

# Install system-level compilers needed for complex Python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["streamlit", "run", "scripts/src/app.py", "--server.port=8501", "--server.address=0.0.0.0"] "--server.port=8080"]