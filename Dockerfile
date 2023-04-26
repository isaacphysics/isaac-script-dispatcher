# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory to /app
WORKDIR /app

# Install Git
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

RUN chmod 600 key.pem

# Export GitHub environment variables
ARG GITHUB_WEBHOOK_SECRET
ENV GITHUB_WEBHOOK_SECRET=$GITHUB_WEBHOOK_SECRET
ARG GITHUB_API_SECRET
ENV GITHUB_API_SECRET=$GITHUB_API_SECRET
ARG GITHUB_APP_IDENTIFIER
ENV GITHUB_APP_IDENTIFIER=$GITHUB_APP_IDENTIFIER
ARG GITHUB_INSTALLATION_ID
ENV GITHUB_INSTALLATION_ID=$GITHUB_INSTALLATION_ID

# Copy the requirements.txt file into the container at /app
COPY requirements.txt /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for the script outputs and input files
RUN mkdir /app/output
RUN mkdir /app/input
RUN mkdir /app/data

# Copy the entire project source into the container at /app
COPY src /app

# Expose the port the app runs on
EXPOSE 5000

# Define environment variable
ENV FLASK_APP app.py

# Set the entrypoint for Gunicorn
ENTRYPOINT ["gunicorn", "app:app", "-c", "gunicorn_config.py"]
