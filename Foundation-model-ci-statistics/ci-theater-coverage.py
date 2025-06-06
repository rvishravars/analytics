import os
import subprocess
import json
import csv
from git import Repo
from tempfile import TemporaryDirectory
from pathlib import Path

projects = [
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
]

IGNORED_LANGS = {"Text", "Markdown", "HTML"}

def run_cloc(path):
    output = subprocess.check_output(["cloc", "--json", path], text=True)
    return json.loads(output)

def find_test_dirs(repo_path):
    return [str(p) for p in Path(repo_path).rglob("*") if p.is_dir() and p.name.lower() in ("test", "tests")]

results = []

with TemporaryDirectory() as tmpdir:
    for project in projects:
        url = f"https://github.com/{project['owner']}/{project['repo']}.git"
        dest = os.path.join(tmpdir, project["name"])
        try:
            print(f"📦 Cloning {project['name']}...")
            Repo.clone_from(url, dest)

            # Total repo SLOC
            cloc_data = run_cloc(dest)
            total_sloc = sum(lang.get("code", 0)
                             for key, lang in cloc_data.items()
                             if key not in ("header", "SUM") and key not in IGNORED_LANGS and isinstance(lang, dict))

            # Test SLOC
            test_sloc = 0
            test_dirs = find_test_dirs(dest)
            if test_dirs:
                test_path = test_dirs[0] if len(test_dirs) == 1 else "--".join([""] + test_dirs)
                test_cloc_data = run_cloc(test_path)
                test_sloc = sum(lang.get("code", 0)
                                for key, lang in test_cloc_data.items()
                                if key not in ("header", "SUM") and key not in IGNORED_LANGS and isinstance(lang, dict))

            percent_test = round((test_sloc / total_sloc) * 100, 1) if total_sloc else 0

            results.append({
                "name": project["name"],
                "Repo URL": f"https://github.com/{project['owner']}/{project['repo']}",
                "Total SLOC": total_sloc,
                "Test SLOC": test_sloc,
                "% Test SLOC": f"{percent_test}%"
            })

        except Exception as e:
            print(f"❌ Failed: {project['name']} → {e}")
            results.append({
                "name": project["name"],
                "Repo URL": f"https://github.com/{project['owner']}/{project['repo']}",
                "Total SLOC": "N/A",
                "Test SLOC": "N/A",
                "% Test SLOC": "N/A"
            })

# Write to CSV
with open("ci_theater_coverage_report.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

print("\n✅ Report saved to ci_theater_coverage_report.csv")
