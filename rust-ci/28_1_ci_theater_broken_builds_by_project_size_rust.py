#!/usr/bin/env python3
import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# --- Project Size Categorization ---
def categorize_project(sloc: int) -> str:
    """Categorizes a project based on its Source Lines of Code (SLOC)."""
    if sloc < 10000:
        return "Small"
    elif sloc < 100000:
        return "Medium"
    else: # sloc >= 100000
        return "Large"

# --- Cohort Processing ---
def process_cohort(broken_builds_file: str, sizes_file: str, cohort_name: str):
    """
    Loads, merges, and prepares data for a single cohort.
    """
    try:
        builds_df = pd.read_csv(broken_builds_file)
        sizes_df = pd.read_csv(sizes_file)
    except FileNotFoundError as e:
        print(f"Error: Input file not found for cohort '{cohort_name}': {e.filename}")
        return None, None

    # Merge dataframes: builds_df has 'name' (owner/repo), sizes_df has 'repo' (owner/repo)
    df = pd.merge(builds_df, sizes_df, left_on="name", right_on="repo", how="inner")

    if df.empty:
        print(f"Warning: No matching projects found for cohort '{cohort_name}'.")
        return None, None

    # Convert metrics to numeric, coercing errors. We'll plot the mean duration of broken stretches.
    metric_to_plot = "Mean Duration"
    df[metric_to_plot] = pd.to_numeric(df[metric_to_plot], errors='coerce')
    df.dropna(subset=[metric_to_plot], inplace=True)

    if df.empty:
        print(f"Warning: No valid numeric data for '{metric_to_plot}' in cohort '{cohort_name}'.")
        return None, None

    # Categorize by size and set order
    df["Size"] = df["rust_sloc"].apply(categorize_project)
    category_order = ["Small", "Medium", "Large"]
    df["Size"] = pd.Categorical(df["Size"], categories=category_order, ordered=True)
    df.sort_values("Size", inplace=True)

    # Print summary statistics
    summary = df.groupby("Size")[metric_to_plot].agg(['mean', 'median', 'count', 'std']).round(2)
    print(f"\n--- Summary for {cohort_name} cohort (Mean Broken Build Duration in Days) ---")
    print(summary)

    return df, category_order

# --- Main Plotting Logic ---
def main():
    parser = argparse.ArgumentParser(
        description="Generate a side-by-side boxplot of broken build durations by project size for Monoglot and Polyglot cohorts."
    )
    # Monoglot args
    parser.add_argument("--mono-broken-builds-file", required=True, help="Path to the monoglot broken builds CSV file.")
    parser.add_argument("--mono-sizes-file", required=True, help="Path to the monoglot project sizes (SLOC) CSV file.")
    # Polyglot args
    parser.add_argument("--poly-broken-builds-file", required=True, help="Path to the polyglot broken builds CSV file.")
    parser.add_argument("--poly-sizes-file", required=True, help="Path to the polyglot project sizes (SLOC) CSV file.")
    # Output arg
    parser.add_argument("--output-file", required=True, help="Path to save the combined output plot PNG file.")
    # Optional cohort names
    parser.add_argument("--mono-cohort-name", default="Monoglot", help="Name for the monoglot cohort.")
    parser.add_argument("--poly-cohort-name", default="Polyglot", help="Name for the polyglot cohort.")

    args = parser.parse_args()

    # Process both cohorts
    print("Processing Monoglot cohort...")
    mono_df, mono_cat_order = process_cohort(
        broken_builds_file=args.mono_broken_builds_file,
        sizes_file=args.mono_sizes_file,
        cohort_name=args.mono_cohort_name
    )

    print("\nProcessing Polyglot cohort...")
    poly_df, poly_cat_order = process_cohort(
        broken_builds_file=args.poly_broken_builds_file,
        sizes_file=args.poly_sizes_file,
        cohort_name=args.poly_cohort_name
    )

    if mono_df is None and poly_df is None:
        print("\nError: Failed to generate plots as no data was available for either cohort.")
        return

    # Create figure with two subplots
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=True)
    #fig.suptitle("Mean Broken Build Stretch Duration by Project Size", fontsize=16)
    
    metric_to_plot = "Mean Duration"
    y_label = "Mean Duration of Broken Stretch (Days)"

    # Plot for monoglot cohort
    if mono_df is not None:
        sns.boxplot(
            data=mono_df, x="Size", y=metric_to_plot, order=mono_cat_order, ax=axes[0],
            showfliers=False, boxprops=dict(facecolor='white')
        )
        axes[0].set_title(f"{args.mono_cohort_name} Projects")
        axes[0].set_xlabel("Project Size")
        axes[0].set_ylabel(y_label)
        axes[0].grid(True, axis='y')
        axes[0].tick_params(axis='x', rotation=10)

    # Plot for polyglot cohort
    if poly_df is not None:
        sns.boxplot(
            data=poly_df, x="Size", y=metric_to_plot, order=poly_cat_order, ax=axes[1],
            showfliers=False, boxprops=dict(facecolor='white')
        )
        axes[1].set_title(f"{args.poly_cohort_name} Projects")
        axes[1].set_xlabel("Project Size")
        axes[1].grid(True, axis='y')
        axes[1].tick_params(axis='x', rotation=10)

    # Final adjustments and save
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
    plt.savefig(args.output_file, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"\n✅ Combined plot saved to {args.output_file}")

if __name__ == "__main__":
    main()