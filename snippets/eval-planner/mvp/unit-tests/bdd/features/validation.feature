Feature: Rule Validation Logic
  As an Eval Engineer
  I want to validate inputs against Python code rules
  So that I can verify agent outputs flexibly

  Scenario: Python Validation Pass
    Given a rule of type "PYTHON" with content:
      """
      import json
      def evaluate(data):
          try:
            d = json.loads(data)
            return d.get("valid", False)
          except:
            return False
      """
    When I validate the input:
      """
      { "valid": true }
      """
    Then the result should be True

  Scenario: Python Validation Fail
    Given a rule of type "PYTHON" with content:
      """
      def evaluate(data):
          return data == "Correct"
      """
    When I validate the input "Wrong"
    Then the result should be False
