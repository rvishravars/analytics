Feature: Job Management
  As an Eval Engineer
  I want to bind a Rule to an Agent (Create a Job)
  So that I can execute the evaluation

  Scenario: Create a valid Job
    Given an Agent named "Staging Bot" with URL "http://localhost:8080"
    And a Rule named "Safety Check" with content:
      """
      async def evaluate(agent_url, auth_config, config):
          return {"passed": True}
      """
    When I create a job binding "Safety Check" to "Staging Bot"
    Then the job should be created successfuly
    And the job status should be "PENDING"
    And the job should link to "Staging Bot"

  Scenario: Execute a job
    Given a Job exists for Rule "Safety Check" and Agent "Staging Bot"
    When I execute the job
    Then the job status should eventually be "COMPLETED"
    And an evaluation result should be recorded
