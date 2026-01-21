from behave import given, when, then
import json
from validation import validate_rule

@given('a rule of type "{rule_type}" with content')
def step_impl(context, rule_type):
    context.rule_type = rule_type
    context.rule_content = context.text

@given('a rule of type "{rule_type}" with content "{content}"')
def step_impl_inline(context, rule_type, content):
    context.rule_type = rule_type
    context.rule_content = content

@when('I validate the input "{input_data}"')
def step_validate_string(context, input_data):
    context.result = validate_rule(context.rule_type, context.rule_content, input_data)

@when('I validate the input')
def step_validate_docstring(context):
    context.result = validate_rule(context.rule_type, context.rule_content, context.text)

@then('the result should be {expected}')
def step_check_result(context, expected):
    expected_bool = True if expected == "True" else False
    assert context.result == expected_bool, f"Expected {expected_bool}, got {context.result}"
