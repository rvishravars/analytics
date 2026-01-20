from typing import Any, Dict

def validate_rule(rule_type: str, content: str, input_data: Any) -> bool:
    """
    Validates input_data against the rule defined by content.
    
    Args:
        rule_type: Must be "PYTHON"
        content: The rule definition (code)
        input_data: The data to validate
        
    Returns:
        bool: True if validation passes, False otherwise.
        
    Raises:
        Exception: If validation logic itself fails.
    """
    try:
        if rule_type == "PYTHON":
            # For MVP: Simple exec usage. 
            # In a real system this must be sandboxed.
            # We expect the code to define a function `evaluate(data) -> bool`
            scope: Dict[str, Any] = {}
            exec(content, scope)
            if "evaluate" not in scope:
                raise ValueError("Python rule must define an 'evaluate' function")
            return scope["evaluate"](input_data)
        
        else:
            raise ValueError(f"Unknown rule_type: {rule_type}")
            
    except Exception as e:
        print(f"Validation Error: {e}")
        raise e
