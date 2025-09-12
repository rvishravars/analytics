import argparse
import os

import pandas as pd
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Plot commit frequency by project size.")
    parser.add_argument(
        "--freq-file", required=True, help="Path to the commit frequency CSV file (e.g., data/20_commit_frequency.csv)."
    )
    parser.add_argument(
        "--sizes-file", required=True, help="Path to the project sizes (SLOC) CSV file (e.g., data/19_rust_sloc.csv)."
    )
    parser.add_argument("--output-file", required=True, help="Path to save the output plot PNG file.")
    args = parser.parse_args()

    # Load commit frequency and project size
    commit_freq_df = pd.read_csv(args.freq_file)
    project_sizes_df = pd.read_csv(args.sizes_file)

    # Merge on project name
    df = pd.merge(commit_freq_df, project_sizes_df[["name", "Category"]], on="name", how="inner")

    # Rename for clarity
    df = df.rename(columns={
        "name": "Project",
        "Avg Commits/Weekday (Mon–Fri)": "Avg_Commits_Weekday",
        "Category": "Size"
    })

    # Convert to numeric
    df["Avg_Commits_Weekday"] = pd.to_numeric(df["Avg_Commits_Weekday"], errors="coerce")

    # Drop NaNs before computing percentiles
    valid_data = df[df["Avg_Commits_Weekday"].notna()]
    median = valid_data["Avg_Commits_Weekday"].median()
    q3 = valid_data["Avg_Commits_Weekday"].quantile(0.75)

    # Plot boxplot of Avg Commits/Weekday grouped by project size
    plt.figure(figsize=(8, 5))
    df.boxplot(column="Avg_Commits_Weekday", by="Size")

    # Add threshold + percentile lines
    plt.axhline(y=2.36, color='red', linestyle='--', label="Infrequent Threshold (2.36)")
    plt.axhline(y=median, color='green', linestyle='--', label=f"Median ({median:.2f})")
    plt.axhline(y=q3, color='orange', linestyle='--', label=f"75th Percentile ({q3:.2f})")

    # Labels and layout
    plt.title("Average Weekday Commits by Project Size")
    plt.suptitle("")
    plt.ylabel("Commits per Weekday")
    plt.ylim(0, 3)
    plt.legend()
    plt.tight_layout()

    os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
    plt.savefig(args.output_file, dpi=300, bbox_inches="tight")
    print(f"✅ Plot saved to {args.output_file}")


if __name__ == "__main__":
    main()
