FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT ["streamlit", "run", "scripts/src/app.py", "--server.port=8080"]