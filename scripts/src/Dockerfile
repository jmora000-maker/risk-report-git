# Step 1: Use an official lightweight Python image
FROM python:3.11-slim

# Step 2: Set the directory inside the cloud container where our app will live
WORKDIR /app

# Step 3: Copy our project files into the cloud container
COPY . /app

# Step 4: Install the required libraries
RUN pip install --no-cache-dir -r requirements.txt

# Step 5: Expose the standard web port
EXPOSE 8080

# Step 6: Tell Streamlit to run on port 8080 and accept outside connections
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]