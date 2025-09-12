import os
import subprocess
import json
import csv
from git import Repo
from tempfile import TemporaryDirectory
from tabulate import tabulate

from ci_foundation_projects import projects

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

            #IGNORED_LANGS = {"Text", "Markdown", "HTML", "JSON", "YAML", "TOML", "CSV", "XML", "CSS", "Jupyter Notebook", "INI", "SVG", ""}
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
with open("data/2_ci_theater_project_sizes.csv", "w", newline="", encoding="utf-8") as csvfile:
    fieldnames = ["name", "SLOC", "Category", "Languages"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

    writer.writeheader()
    for row in results:
        writer.writerow(row)

print("\nResults written to 2_ci_theater_project_sizes.csv")
