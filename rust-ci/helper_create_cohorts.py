#!/usr/bin/env python3
"""
Helper script to generate Python project lists from the CSVs produced by
29_collect_language_sloc.py.
"""
import argparse
import pandas as pd

def get_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate cohort project list files from summary CSVs.")
    parser.add_argument(
        "--monoglot-summary",
        default="data/29_monoglot_rust_repos_summary.csv",
        help="Path to the monoglot summary CSV.",
    )
    parser.add_argument(
        "--polyglot-summary",
        default="data/29_polyglot_rust_repos_summary.csv",
        help="Path to the polyglot summary CSV.",
    )
    parser.add_argument("--monoglot-output", default="rust_repos_monoglot.py", help="Output file for monoglot projects.")
    parser.add_argument("--polyglot-output", default="rust_repos_polyglot.py", help="Output file for polyglot projects.")
    return parser.parse_args()

def create_project_list_file(input_csv: str, output_py: str, repo_col: str = 'repo'):
    """Reads a CSV and writes a Python list file."""
    try:
        df = pd.read_csv(input_csv)
        projects = df[repo_col].tolist()
        with open(output_py, 'w', encoding='utf-8') as f:
            f.write("projects = [\n")
            for p in projects:
                f.write(f'  "{p}",\n')
            f.write("]\n")
        print(f"✅ Created {output_py} with {len(projects)} projects.")
    except FileNotFoundError:
        print(f"⚠️  Warning: Could not find {input_csv}. Skipping.")
    except KeyError:
        print(f"⚠️  Warning: Column '{repo_col}' not found in {input_csv}. Skipping.")

def main():
    """Generates the cohort files."""
    args = get_args()
    create_project_list_file(args.monoglot_summary, args.monoglot_output)
    create_project_list_file(args.polyglot_summary, args.polyglot_output)

if __name__ == "__main__":
    main()