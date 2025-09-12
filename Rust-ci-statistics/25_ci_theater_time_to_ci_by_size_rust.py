import argparse
import os

import pandas as pd
import matplotlib.pyplot as plt


def categorize_project(sloc: int) -> str:
    """Categorizes a project based on its Source Lines of Code (SLOC)."""
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


def main():
    parser = argparse.ArgumentParser(
        description="Generate a boxplot of time to first CI adoption by project size for a specific cohort."
    )
    parser.add_argument(
        "--stats-file",
        required=True,
        help="Path to the stats CSV file (e.g., from 23_github_project_statistics_rust.py).",
    )
    parser.add_argument(
        "--sizes-file",
        required=True,
        help="Path to the repo summary CSV file with SLOC (e.g., from 29_ci_theater_polyglot_rust.py).",
    )
    parser.add_argument("--output-file", required=True, help="Path to save the output plot PNG file.")
    parser.add_argument(
        "--cohort-name",
        required=True,
        help="Name of the cohort (e.g., 'Monoglot' or 'Polyglot') for the plot title.",
    )
    args = parser.parse_args()

    try:
        stats_df = pd.read_csv(args.stats_file)
        sizes_df = pd.read_csv(args.sizes_file)
    except FileNotFoundError as e:
        print(f"Error: Input file not found: {e.filename}")
        print("Please ensure you have run the prerequisite scripts for both stats and sizes.")
        return

    sizes_df["Category"] = sizes_df["rust_sloc"].apply(categorize_project)
    df = pd.merge(stats_df, sizes_df[["repo", "Category"]], left_on="Project", right_on="repo", how="inner")

    df = df.rename(columns={"Time to First CI (months)": "Time_To_First_CI", "Category": "Size"})
    df = df.drop(columns=["repo"])

    df["Time_To_First_CI"] = pd.to_numeric(df["Time_To_First_CI"], errors="coerce")
    df.dropna(subset=["Time_To_First_CI"], inplace=True)

    if df.empty:
        print("\nError: No valid data to plot after merging and cleaning.")
        return

    category_order = ["Very Small", "Small", "Medium", "Large", "Very Large"]
    df["Size"] = pd.Categorical(df["Size"], categories=category_order, ordered=True)
    df.sort_values("Size", inplace=True)

    plt.figure(figsize=(10, 6))
    df.boxplot(column="Time_To_First_CI", by="Size", grid=True)
    plt.title(f"Time to First CI Adoption by Project Size ({args.cohort_name} Projects)")
    plt.suptitle("")
    plt.xlabel("Project Size")
    plt.ylabel("Months from Repo Creation")
    plt.xticks(rotation=10)
    plt.tight_layout()

    os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
    plt.savefig(args.output_file, dpi=300, bbox_inches="tight")
    print(f"✅ Plot saved to {args.output_file}")


if __name__ == "__main__":
    main()
