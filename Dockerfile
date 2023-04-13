# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory to /app
WORKDIR /app

# Install Git
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

# Set up keys for GitHub
ARG SSH_PRIVATE_KEY
RUN mkdir -p ~/.ssh && chmod 700 ~/.ssh && \
    echo "${SSH_PRIVATE_KEY}" > ~/.ssh/id_ed25519 && \
    chmod 600 ~/.ssh/id_ed25519 && \
    ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts
ARG APP_PRIVATE_KEY
RUN echo "${APP_PRIVATE_KEY}" > key.pem && \
    chmod 600 key.pem

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

# Create a directory for the script outputs
RUN mkdir /app/output

# Copy the entire project source into the container at /app
COPY src /app

# Expose the port the app runs on
EXPOSE 5000

# Define environment variable
ENV FLASK_APP app.py

# Set the entrypoint for Gunicorn
ENTRYPOINT ["gunicorn", "app:app", "-c", "gunicorn_config.py"]
