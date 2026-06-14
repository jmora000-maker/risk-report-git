# Use the official Python slim image
FROM python:3.11-slim

EXPOSE 8080

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
COPY . /app

# Force Streamlit to listen to port 8501 and bind to all network interfaces
ENTRYPOINT ["streamlit", "run", "scripts/src/app.py", "--server.port=8080", "--server.address=0.0.0.0"]
