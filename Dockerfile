
# Use the official Playwright image which includes browsers and system dependencies
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Set working directory inside the container
WORKDIR /app

# Copy requirements first to leverage Docker cache
# Assuming requirements.txt is in backend/requirements.txt
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
# The base image includes browsers, but running install ensures compatibility
RUN playwright install chromium

# Copy the application code
# We copy the contents of the 'backend' directory into the root of the container workdir
COPY backend/ .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
# Removing EXPOSE to let Railway route to PORT automatically

# Command to run the application
# Use shell form to expand $PORT variable with a default fallback and exec to pass signals
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'
