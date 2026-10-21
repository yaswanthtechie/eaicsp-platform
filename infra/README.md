# Shared Infrastructure Environment

## Overview

This directory contains the shared local infrastructure for the EAICSP platform.

## Services

The default Docker Compose stack includes:

- PostgreSQL: shared database with service-specific schemas and users
- Kafka: event streaming
- Redis: caching
- ClickHouse: analytical queries
- MongoDB: document storage
- MinIO: S3-compatible object storage
- InfluxDB: time-series storage
- MLflow: experiment tracking and model registry

## Requirements

- Docker Desktop with Docker Compose
- Python and the project virtual environment for seed generation
- A configured `.env` file in the repository root

The full stack can require substantial memory. Use the low-memory profile for local development when needed.

## Start the full stack

Run from the repository root:

```powershell
docker compose --env-file .env -f infra/docker-compose.yml up -d --wait
