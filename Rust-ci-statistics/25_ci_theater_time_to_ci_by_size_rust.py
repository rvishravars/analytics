import argparse
import os

import pandas as pd
import matplotlib.pyplot as plt


def categorize_project(sloc: int) -> str:
    """Categorizes a project based on its Source Lines of Code (SLOC)."""
    if sloc < 10000:
        return "Small"
    elif sloc < 100000:
        return "Medium"
    else:
        return "Large"


def generate_plot(stats_file: str, sizes_file: str, cohort_name: str, ax) -> bool:
    try:
        stats_df = pd.read_csv(stats_file)
        sizes_df = pd.read_csv(sizes_file)
    except FileNotFoundError as e:
        print(f"Error: Input file not found: {e.filename}")
        print("Please ensure you have run the prerequisite scripts for both stats and sizes.")
        return False

    sizes_df["Category"] = sizes_df["rust_sloc"].apply(categorize_project)
    df = pd.merge(stats_df, sizes_df[["repo", "Category"]], left_on="Project", right_on="repo", how="inner")
    df = df.rename(columns={"Time to First CI (months)": "Time_To_First_CI", "Category": "Size"})
    df = df.drop(columns=["repo"])

    df["Time_To_First_CI"] = pd.to_numeric(df["Time_To_First_CI"], errors="coerce")
    df.dropna(subset=["Time_To_First_CI"], inplace=True)

    if df.empty:
        print(f"\nError: No valid data to plot for cohort '{cohort_name}' after merging and cleaning.")
        return False

    category_order = ["Small", "Medium", "Large"]
    df["Size"] = pd.Categorical(df["Size"], categories=category_order, ordered=True)
    df.sort_values("Size", inplace=True)

    # Create boxplot on provided axis
    df.boxplot(column="Time_To_First_CI", by="Size", grid=True, ax=ax, patch_artist=True, boxprops=dict(facecolor='white'), showfliers=False)
    ax.set_title(f"{cohort_name} Projects")
    ax.set_xlabel("Project Size")
    ax.set_ylabel("Months from Repo Creation")
    for tick in ax.get_xticklabels():
        tick.set_rotation(10)

    # Print summary statistics: mean, 1st quantile, and 3rd quantile
    summary = df.groupby("Size")["Time_To_First_CI"].agg(
        mean="mean",
        q1=lambda x: x.quantile(0.25),
        q3=lambda x: x.quantile(0.75)
    )
    print(f"\nSummary for {cohort_name} cohort:")
    print(summary)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Generate a combined boxplot of time to first CI adoption by project size for Monoglot and Polyglot cohorts."
    )

    # Monoglot arguments
    parser.add_argument("--mono-stats-file", required=True, help="Path to the monoglot stats CSV file (e.g., from 23_github_project_statistics_rust.py).")
    parser.add_argument("--mono-sizes-file", required=True, help="Path to the monoglot repo summary CSV with SLOC (e.g., from 29_collect_language_sloc.py).")
    parser.add_argument("--mono-cohort-name", required=True, help="Name of the monoglot cohort for the plot title.")

    # Polyglot arguments
    parser.add_argument("--poly-stats-file", required=True, help="Path to the polyglot stats CSV file (e.g., from 23_github_project_statistics_rust.py).")
    parser.add_argument("--poly-sizes-file", required=True, help="Path to the polyglot repo summary CSV with SLOC (e.g., from 29_collect_language_sloc.py).")
    parser.add_argument("--poly-cohort-name", required=True, help="Name of the polyglot cohort for the plot title.")

    # Combined output file
    parser.add_argument("--output-file", required=True, help="Path to save the combined output plot PNG file.")

    args = parser.parse_args()

    # Create a single figure with two subplots side by side
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    print("Processing Monoglot cohort...")
    mono_result = generate_plot(
        stats_file=args.mono_stats_file,
        sizes_file=args.mono_sizes_file,
        cohort_name=args.mono_cohort_name,
        ax=axes[0],
    )

    print("\nProcessing Polyglot cohort...")
    poly_result = generate_plot(
        stats_file=args.poly_stats_file,
        sizes_file=args.poly_sizes_file,
        cohort_name=args.poly_cohort_name,
        ax=axes[1],
    )

    if not mono_result or not poly_result:
        print("\nError: One or more plots failed to generate.")
    else:
        # Set a global title
        #fig.suptitle("Time to First CI Adoption by Project Size", fontsize=16)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
        plt.savefig(args.output_file, dpi=300, bbox_inches="tight")
        print(f"\n✅ Combined plot saved to {args.output_file}")


if __name__ == "__main__":
    main()