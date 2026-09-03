# Use Python base image pinned to specific hash for reproducible builds
FROM python:3.11-slim@sha256:e8b3e8e1a7f6ede4ed559bdcef300a9f3f85a9d2a2db336cbcb5bb2412f0a3cd

WORKDIR /app

# Copy and install dependencies
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY app/math_agent/ ./math_agent/

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import requests; requests.get('http://localhost:8080/ping')"]

# Expose port for AgentCore Runtime
EXPOSE 8080

# Run the agent
CMD ["python", "math_agent/main.py"]