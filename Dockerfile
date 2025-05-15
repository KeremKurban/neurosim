# Use Python 3.11 as base image
FROM python:3.11-slim

# Install essential build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    git \
    curl \
    python3-dev \
    openmpi-bin \
    libopenmpi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 neurosim

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ src/

# Install dependencies and project
RUN uv venv /app/.venv && \
    chown -R neurosim:neurosim /app
ENV PATH="/app/.venv/bin:$PATH"
RUN uv pip install -e .

# Switch to non-root user
USER neurosim

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV NEURON_MODULE_PATH=/app/.venv/lib/python3.11/site-packages/neuron

# Set NEURON environment variables
ENV PYTHONPATH=/app/src:$PYTHONPATH
ENV PATH=/app/.venv/bin:$PATH
ENV NEURON_HOME=/app/.venv

# Command to run the service
CMD ["uvicorn", "neurosim.api.main:app", "--host", "0.0.0.0", "--port", "8000"]