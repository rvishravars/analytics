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

## 🌐 Networking & Connectivity

The application uses a dedicated Docker network named `eval-planner-network`.

### Connecting External Agents
If your evaluation agent is running in a separate Docker container (e.g., the sample agent in `integration-test`), it must be on the same network as the API to communicate correctly.

1. **Run the agent container**:
   ```bash
   sudo ./integration-test/run_agent.sh
   ```

2. **Connect it to the application network**:
   ```bash
   sudo docker network connect eval-planner-network sample-agent-container
   ```

3. **Register the agent** using the internal container name:
   - **Agent URL**: `http://sample-agent-container:8081`

### Running Integration Tests
The integration test container is automatically attached to `eval-planner-network` by the `run_integration_docker.sh` script, allowing it to "see" the `api` service.

---

## 🛠 Project Structure

- `source/`: Contains the core application (Backend & Frontend) and Docker configuration.
- `unit-tests/`: Contains the BDD test suite and Docker-based test runner.
- `integration-test/`: Contains end-to-end API scripts and a sample agent for local testing.
- `mvp.md`: The original requirements and architecture document.
