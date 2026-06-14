# Use the official Python slim image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install standard Linux build tools required by Pandas
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file from the root 'main' folder
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything else from your 'main' directory (including scripts/ folder)
COPY . .

# Inform Docker that the container listens on port 8501 at runtime
EXPOSE 3000

# Configure a health check using Streamlit's built-in endpoint
HEALTHCHECK CMD curl --fail http://localhost:3000/_stcore/health || exit 1

# Force Streamlit to listen to port 8501 and bind to all network interfaces
ENTRYPOINT ["streamlit", "run", "scripts/src/app.py", "--server.port=3000", "--server.address=0.0.0.0"]
