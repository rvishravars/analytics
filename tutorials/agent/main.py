import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path="/home/vishravars/code/analytics/tutorials/agent/.env")

from langchain.agents import create_agent
from langchain.tools import tool

@tool('get-weather', description='Return weather information for a given city', return_direct=False)
def get_weather(city: str):
	"""Fetch weather for a city from wttr.in in JSON format."""
	if not city:
		raise ValueError("city must be provided")
	url = f"https://wttr.in/{city}?format=j1"
	resp = requests.get(url, timeout=10)
	resp.raise_for_status()
	try:
		return resp.json()
	except ValueError:
		# return raw text on JSON parse failure
		return {"error": "Invalid JSON response", "text": resp.text}

# Add a constant for the system prompt so we don't try to call the StructuredTool
DEFAULT_SYSTEM_PROMPT = "You are a helpful weather assistant who always cracks jokes while remaining helpful."

@tool('system_prompt', description='Return a system prompt string to guide the agent', return_direct=True)
def system_prompt():
	"""Return a fixed system prompt used to guide the agent's behavior."""
	return DEFAULT_SYSTEM_PROMPT

def create_weather_agent():
	agent = create_agent(
        model = 'gpt-4.1-mini',
		tools = [get_weather, system_prompt],
		# pass the prompt string directly (don't call the StructuredTool)
		system_prompt=DEFAULT_SYSTEM_PROMPT
	)
	return agent

def main():
	# placeholder main to ensure the module is importable
	print("main module loaded - environment variables are loaded")
	agent = create_weather_agent()
	# Example / demonstration run (safe default). Replace or remove in production.
	prompt = "Get the current weather for London."
	try:
		result = agent.invoke({
                'messages': [
                    {'role': 'user', 'content': 'What is the weather like in Vienna?'}
                ]
            }
        )
		print("Agent result:", result)
		
	except Exception as e:
		print("Agent call failed:", e)


if __name__ == "__main__":
	main()

