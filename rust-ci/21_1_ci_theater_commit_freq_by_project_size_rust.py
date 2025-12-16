#!/usr/bin/env python3
import argparse
import os

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def categorize_project(sloc: int) -> str:
    """Categorizes a project based on its Source Lines of Code (SLOC)."""
    if sloc < 10000:
        return "Small"
    elif sloc < 100000:
        return "Medium"
    else:
        return "Large"


def process_cohort(freq_file: str, sizes_file: str, cohort_name: str):
    try:
        commit_freq_df = pd.read_csv(freq_file)
        project_sizes_df = pd.read_csv(sizes_file)
    except FileNotFoundError as e:
        print(f"Error: Input file not found: {e.filename}")
        return None, None, None

    project_sizes_df["Category"] = project_sizes_df["rust_sloc"].apply(categorize_project)
    # Merge on project name. The freq file has 'name', sizes file has 'repo'.
    df = pd.merge(
        commit_freq_df,
        project_sizes_df[["repo", "Category"]],
        left_on="name",
        right_on="repo",
        how="inner"
    )

    # Handle potential merge issues due to malformed 'name' column in the freq file.
    if df.empty and not commit_freq_df.empty and 'Last Commit Date' in commit_freq_df.columns:
        if isinstance(commit_freq_df['Last Commit Date'].iloc[0], str):
            print(f"Warning: [{cohort_name}] Initial merge failed. Attempting to fix malformed 'name' column in frequency file.")
            commit_freq_df['repo_slug'] = commit_freq_df['name'].astype(str) + '/' + commit_freq_df['Last Commit Date'].astype(str)
            df = pd.merge(
                commit_freq_df,
                project_sizes_df[["repo", "Category"]],
                left_on="repo_slug",
                right_on="repo",
                how="inner"
            )

    # Detect correct commit frequency column.
    avg_commit_col_new = "Avg_Commits_Weekday"
    avg_commit_col_legacy = "Avg Commits/Weekday (Mon–Fri)"
    avg_commit_col_malformed = "Weekday (Mon–Fri)"

    if avg_commit_col_new in df.columns:
        avg_commit_col = avg_commit_col_new
    elif avg_commit_col_legacy in df.columns:
        avg_commit_col = avg_commit_col_legacy
    elif avg_commit_col_malformed in df.columns:
        print(f"Warning: [{cohort_name}] Using fallback column '{avg_commit_col_malformed}' for commit frequency due to potentially malformed CSV header.")
        avg_commit_col = avg_commit_col_malformed
    else:
        print(f"Error: [{cohort_name}] Could not find commit frequency column. Available columns: {df.columns.tolist()}")
        return None, None, None

    # Rename columns for clarity.
    df = df.rename(columns={
        "name": "Project",
        avg_commit_col: "Avg_Commits_Weekday",
        "Category": "Size"
    })

    # Ensure commit frequency is numeric.
    df["Avg_Commits_Weekday"] = pd.to_numeric(df["Avg_Commits_Weekday"], errors="coerce")
    valid_data = df[df["Avg_Commits_Weekday"].notna()]
    if valid_data.empty:
        print(f"No valid data to plot for {cohort_name}.")
        return None, None, None

    # Print summary statistics by category
    summary = valid_data.groupby("Size")["Avg_Commits_Weekday"].agg(
        mean='mean',
        first_quartile=lambda x: x.quantile(0.25),
        third_quartile=lambda x: x.quantile(0.75)
    ).round(2)
    print(f"\n--- Summary for {cohort_name} cohort (Commits per Weekday) ---")
    print(summary)

    median = valid_data["Avg_Commits_Weekday"].median()
    q3 = valid_data["Avg_Commits_Weekday"].quantile(0.75)

    category_order = ["Small", "Medium", "Large"]
    df['Size'] = pd.Categorical(df['Size'], categories=category_order, ordered=True)
    df.sort_values('Size', inplace=True)

    return df, median, q3


def main():
    parser = argparse.ArgumentParser(
        description="Combined plot: Commit frequency by project size for monoglot and polyglot cohorts."
    )
    parser.add_argument("--mono-freq-file", required=True, help="Path to the monoglot commit frequency CSV file.")
    parser.add_argument("--mono-sizes-file", required=True, help="Path to the monoglot project sizes (SLOC) CSV file.")
    parser.add_argument("--poly-freq-file", required=True, help="Path to the polyglot commit frequency CSV file.")
    parser.add_argument("--poly-sizes-file", required=True, help="Path to the polyglot project sizes (SLOC) CSV file.")
    parser.add_argument("--output-file", required=True, help="Path to save the output combined plot PNG file.")
    parser.add_argument("--mono-cohort-name", default="Monoglot", help="Name of the monoglot cohort.")
    parser.add_argument("--poly-cohort-name", default="Polyglot", help="Name of the polyglot cohort.")
    args = parser.parse_args()

    mono_df, mono_median, mono_q3 = process_cohort(args.mono_freq_file, args.mono_sizes_file, args.mono_cohort_name)
    poly_df, poly_median, poly_q3 = process_cohort(args.poly_freq_file, args.poly_sizes_file, args.poly_cohort_name)

    if mono_df is None and poly_df is None:
        print("No valid data to plot for either cohort.")
        return

    category_order = ["Small", "Medium", "Large"]

    # Create a figure with two subplots side by side.
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=True)

        # Plot for monoglot cohort.
    if mono_df is not None:
        sns.boxplot(
            data=mono_df,
            x="Size",
            y="Avg_Commits_Weekday",
            order=category_order,
            ax=axes[0],
            showfliers=False,  # Outliers removed
            boxprops=dict(facecolor='white')
        )
        axes[0].set_title(f"{args.mono_cohort_name} Projects")
        axes[0].set_xlabel("Project Size Category")
        axes[0].set_ylabel("Commits per Weekday")
        axes[0].set_ylim(0, 5.0)
        axes[0].grid(True, axis='y')
        axes[0].tick_params(axis='x', rotation=10)

    # Plot for polyglot cohort.
    if poly_df is not None:
        sns.boxplot(
            data=poly_df,
            x="Size",
            y="Avg_Commits_Weekday",
            order=category_order,
            ax=axes[1],
            showfliers=False,  # Outliers removed
            boxprops=dict(facecolor='white')
        )
        axes[1].set_title(f"{args.poly_cohort_name} Projects")
        axes[1].set_xlabel("Project Size Category")
        axes[1].set_ylim(0, 5.0)
        axes[1].grid(True, axis='y')
        axes[1].tick_params(axis='x', rotation=10)

    #plt.suptitle("Average Weekday Commits by Project Size")
    plt.tight_layout(rect=[0, 0, 1, 0.95])

    os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
    plt.savefig(args.output_file, dpi=300, bbox_inches='tight')
    print(f"✅ Combined plot saved to {args.output_file}")


if __name__ == "__main__":
    main()