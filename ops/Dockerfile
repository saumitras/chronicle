FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Install shared-events package first
COPY shared-events/ ./shared-events/
RUN uv pip install --system -e ./shared-events

# Install service dependencies
ARG SERVICE
COPY ${SERVICE}/pyproject.toml ./pyproject.toml
RUN uv pip install --system .

# Copy service source into /app directly so packages are importable
COPY ${SERVICE}/ ./

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
