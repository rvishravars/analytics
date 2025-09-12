#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt
import argparse
import seaborn as sns


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


# --- Main ---
def main():
    """
    Generates box plots comparing CI build brokenness metrics against project size.
    """
    parser = argparse.ArgumentParser(description="Generate boxplots of broken build metrics by project size.")
    parser.add_argument(
        "--broken-builds-file",
        required=True,
        help="Path to the broken builds CSV file (from 28_ci_theater_broken_builds_rust.py).",
    )
    parser.add_argument(
        "--sizes-file",
        required=True,
        help="Path to the repo summary CSV file with SLOC (from 29_ci_theater_polyglot_rust.py).",
    )
    parser.add_argument(
        "--output-stretches-plot", required=True, help="Path to save the broken stretches plot."
    )
    parser.add_argument(
        "--output-max-days-plot", required=True, help="Path to save the max broken days plot."
    )
    parser.add_argument(
        "--cohort-name",
        required=True,
        help="Name of the cohort for plot titles (e.g., 'Monoglot' or 'Polyglot').",
    )
    args = parser.parse_args()

    # Load data
    try:
        broken_builds_df = pd.read_csv(args.broken_builds_file)
        project_sizes_df = pd.read_csv(args.sizes_file)
    except FileNotFoundError as e:
        print(f"Error: Missing required CSV file: {e.filename}")
        print("Please run the prerequisite scripts first.")
        return

    # Merge on project name
    project_sizes_df["Category"] = project_sizes_df["rust_sloc"].apply(categorize_project)
    df = pd.merge(broken_builds_df, project_sizes_df[["repo", "Category"]], left_on="name", right_on="repo", how="inner")

    # Clean and convert relevant fields
    df["Broken >2 Days"] = pd.to_numeric(df["Broken >2 Days"], errors="coerce")
    df["Max Broken Days"] = pd.to_numeric(df["Max Broken Days"], errors="coerce")
    df["Runs Analyzed"] = pd.to_numeric(df["Runs Analyzed"], errors="coerce")

    # Filter out projects with no build data or where analysis failed
    df.dropna(subset=["Broken >2 Days", "Max Broken Days"], inplace=True)
    df = df[df["Runs Analyzed"] > 0]

    if df.empty:
        print("No valid data to plot after merging and cleaning. Exiting.")
        return

    # Define the order of categories for plotting
    category_order = ["Very Small", "Small", "Medium", "Large", "Very Large"]
    df['Category'] = pd.Categorical(df['Category'], categories=category_order, ordered=True)
    df.sort_values('Category', inplace=True)

    # --- Plot 1: Number of long broken build stretches (>2 days) ---
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x="Category", y="Broken >2 Days", order=category_order)

    median_val = df["Broken >2 Days"].median()
    plt.axhline(y=median_val, color='green', linestyle='--', label=f"Overall Median ({median_val:.2f})")

    plt.title(f"Count of Long Broken Build Stretches (>2 Days) by Project Size ({args.cohort_name} Projects)")
    plt.suptitle("")
    plt.xlabel("Project Size Category")
    plt.ylabel("Number of Stretches > 2 Days")
    plt.xticks(rotation=10)
    plt.legend()
    plt.grid(True, axis='y')
    plt.tight_layout()

    out_path1 = args.output_stretches_plot
    os.makedirs(os.path.dirname(out_path1) or ".", exist_ok=True)
    plt.savefig(out_path1, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to {out_path1}")
    plt.close()

    # --- Plot 2: Maximum duration of a broken build stretch ---
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x="Category", y="Max Broken Days", order=category_order)

    plt.title(f"Maximum Broken Build Duration by Project Size ({args.cohort_name} Projects)")
    plt.suptitle("")
    plt.xlabel("Project Size Category")
    plt.ylabel("Max Days Build Remained Broken")
    plt.xticks(rotation=10)
    plt.grid(True, axis='y')
    plt.tight_layout()

    out_path2 = args.output_max_days_plot
    os.makedirs(os.path.dirname(out_path2) or ".", exist_ok=True)
    plt.savefig(out_path2, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to {out_path2}")
    plt.close()

if __name__ == "__main__":
    main()