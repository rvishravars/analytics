# Agentic Eval MVP

This project is a Minimum Viable Product (MVP) for an Agentic Evaluation system. It follows a fully containerized architecture using Docker and Docker Compose.

## 🚀 Deployment

The entire application (Database, Backend API, and Frontend UI) can be deployed using the following steps:

1.  Navigate to the source directory:
    ```bash
    cd source/
    ```
2.  Run the deployment script:
    ```bash
    sudo ./deploy.sh
    ```
3.  Access the services:
    - **Dashboard**: [http://localhost:3000](http://localhost:3000)
    - **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

To stop the services, run `./undeploy.sh`.

---

## 🧪 Testing

The project includes two types of containerized test suites. No local Python or dependency setup is required on your host machine.

### 1. Behavior Driven Development (BDD) Tests
This suite verifies the core business logic (Agent Management, Job Management, and Validation Rules) using a dedicated Docker container and an internal SQLite database.

- **Run command**: 
  ```bash
  ./unit-tests/bdd/run_bdd_docker.sh
  ```

### 2. Integration Tests
This suite verifies the end-to-end evaluation workflow by making real API calls to the deployed services. It ensures that Rules can be bound to Agents and executed correctly.

- **Prerequisite**: Ensure the application is deployed (`./source/deploy.sh`).
- **Run command**: 
  ```bash
  ./integration-test/run_integration_docker.sh
  ```

---

## 🛠 Project Structure

- `source/`: Contains the core application (Backend & Frontend) and Docker configuration.
- `unit-tests/`: Contains the BDD test suite and Docker-based test runner.
- `integration-test/`: Contains end-to-end API scripts and a sample agent for local testing.
- `mvp.md`: The original requirements and architecture document.

---

## 💡 Connecting Local Agents
When running tests or using the UI, if your agent is running in a Docker container (like the one in `integration-test`), use the **internal Docker DNS name** for registration:

- **Agent URL**: `http://sample-agent-container:8081`

If you encounter network isolation issues, ensure the agent container is connected to the application network:
```bash
sudo docker network connect source_default sample-agent-container
```
