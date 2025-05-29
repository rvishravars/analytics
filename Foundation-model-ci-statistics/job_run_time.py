import os
import requests
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

# API endpoint for the specific workflow run
run_id = 8635894934
url = f"https://api.github.com/repos/google-research/t5x/actions/runs/{run_id}"

response = requests.get(url, headers=headers)

if response.status_code == 200:
    data = response.json()
    print("Run started at:", data["run_started_at"])
else:
    print("Error:", response.status_code, response.text)
