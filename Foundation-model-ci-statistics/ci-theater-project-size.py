import os
import subprocess
import json
import csv
from git import Repo
from tempfile import TemporaryDirectory
from tabulate import tabulate

"""projects = [
    {"name": "t5", "owner": "google-research", "repo": "text-to-text-transfer-transformer"},
    {"name": "Qwen", "owner": "QwenLM", "repo": "Qwen"},
    {"name": "Qwen3", "owner": "QwenLM", "repo": "Qwen3"},
    {"name": "RWKV-LM", "owner": "BlinkDL", "repo": "RWKV-LM"},
    {"name": "gpt-neox", "owner": "EleutherAI", "repo": "gpt-neox"},
    {"name": "OpenAI-CLIP", "owner": "openai", "repo": "CLIP"},
    {"name": "Yalm", "owner": "yandex", "repo": "YaLM-100B"},
    {"name": "Dbrx", "owner": "databricks", "repo": "dbrx"},
    {"name": "Yi", "owner": "01-ai", "repo": "Yi"},
    {"name": "Deepseek-V3", "owner": "deepseek-ai", "repo": "DeepSeek-V3"},
    {"name": "Deepseek-Janus", "owner": "deepseek-ai", "repo": "Janus"},
    {"name": "YuE", "owner": "multimodal-art-projection", "repo": "YuE"},
    {"name": "ChronosForecasting", "owner": "amazon-science", "repo": "chronos-forecasting"},
    {"name": "InternVideo", "owner": "OpenGVLab", "repo": "InternVideo"},
    {"name": "lag-llama", "owner": "time-series-foundation-models", "repo": "lag-llama"},
    {"name": "Otter", "owner": "EvolvingLMMs-Lab", "repo": "Otter"},
    {"name": "Clay-foundation-model", "owner": "Clay-foundation", "repo": "model"},
    {"name": "whisper", "owner": "openai", "repo": "whisper"},
    {"name": "microsoft-industrial-foundation-models", "owner": "microsoft", "repo": "Industrial-Foundation-Models"},
    {"name": "microsoft-BioGPT", "owner": "microsoft", "repo": "BioGPT"},
    {"name": "RadFM", "owner": "chaoyi-wu", "repo": "RadFM"},
    {"name": "roberta_zh", "owner": "brightmart", "repo": "roberta_zh"},
    {"name": "Ernie", "owner": "PaddlePaddle", "repo": "ERNIE"},
    {"name": "ChatGlm-6B", "owner": "THUDM", "repo": "ChatGLM-6B"},
    {"name": "Hibiki", "owner": "kyutai-labs", "repo": "hibiki"}
]"""

projects = [
    {"name": "Yi", "owner": "01-ai", "repo": "Yi"}
]

def categorize_project(sloc):
    if sloc < 1000:
        return "Very Small"
    elif sloc < 10000:
        return "Small"
    elif sloc < 100000:
        return "Medium"
    elif sloc < 1000000:
        return "Large"
    else:
        return "Very Large"

results = []

with TemporaryDirectory() as tmpdir:
    for project in projects:
        url = f"https://github.com/{project['owner']}/{project['repo']}.git"
        dest = os.path.join(tmpdir, project['name'])
        try:
            print(f"Cloning {project['name']}...")
            Repo.clone_from(url, dest)

            output = subprocess.check_output(["cloc", "--json", dest], text=True)
            cloc_data = json.loads(output)

            #IGNORED_LANGS = {"Text", "Markdown", "HTML", "JSON", "YAML", "TOML"}
            IGNORED_LANGS = {}

            sloc = sum(lang.get("code", 0)
                    for key, lang in cloc_data.items()
                    if key not in ("header", "SUM") and key not in IGNORED_LANGS and isinstance(lang, dict))

            languages = [
                f"{key} ({lang['code']})"
                for key, lang in cloc_data.items()
                if key not in ("header", "SUM") and key not in IGNORED_LANGS and isinstance(lang, dict)
            ]

            results.append({
                "name": project["name"],
                "SLOC": sloc,
                "Category": categorize_project(sloc),
                "Languages": ", ".join(languages)
            })
        except Exception as e:
            print(f"Failed {project['name']}: {e}")
            results.append({
                "name": project["name"],
                "SLOC": "N/A",
                "Category": "Error",
                "Languages": "N/A"
            })

# Print results to console
print(tabulate(results, headers="keys", tablefmt="grid"))

# Write to CSV
with open("ci_theater_project_sizes.csv", "w", newline="", encoding="utf-8") as csvfile:
    fieldnames = ["name", "SLOC", "Category", "Languages"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

    writer.writeheader()
    for row in results:
        writer.writerow(row)

print("\nResults written to ci_theater_project_sizes.csv")
