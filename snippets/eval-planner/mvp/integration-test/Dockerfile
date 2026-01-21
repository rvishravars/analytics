FROM python:3.9-slim

WORKDIR /app

# Install dependencies
RUN pip install fastapi uvicorn pydantic

# Copy source code
COPY sample_agent.py .

# Expose port
EXPOSE 8081

# Run the application
CMD ["uvicorn", "sample_agent:app", "--host", "0.0.0.0", "--port", "8081"]
