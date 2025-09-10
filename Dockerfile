# Use an official Python runtime as a parent image for a lean image size
FROM python:3.10-slim-bookworm

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container and install dependencies
# This step is placed early to leverage Docker's build cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project directory into the container's /app directory.
# This includes src/, static/, and other root-level files.
COPY . .

# Expose the port that FastAPI will run on
EXPOSE 8000

# Define the command to run your application using Uvicorn
# 'src.main:app' tells Uvicorn to look for the 'app' object in 'main.py' inside the 'src' directory.
CMD ["uvicorn", "backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]