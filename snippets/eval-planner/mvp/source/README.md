# Agentic Eval MVP

This is the Minimal Viable Product (MVP) source code for the Agentic Evaluation System Rule Manager.

## Architecture
- **Frontend**: React (served via Nginx)
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL

## Prerequisites
- Docker
- Docker Compose

## How to Deploy

1.  Navigate to this directory:
    ```bash
    cd mvp/source
    ```

2.  Make the deploy script executable:
    ```bash
    chmod +x deploy.sh
    ```

3.  Run the deployment script:
    ```bash
    ./deploy.sh
    ```

4.  Access the application:
    - **Dashboard**: [http://localhost:3000](http://localhost:3000)
    - **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

## Development

- **Backend**: Located in `backend/`. Uses `uvicorn` with auto-reload if running locally outside Docker.
- **Frontend**: Located in `frontend/`. Standard React app structure.

## Stopping the App

To stop and remove the containers:
```bash
docker-compose down
```
