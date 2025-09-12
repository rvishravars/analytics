#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import argparse


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
    """
    Generates plots comparing the change in bug-like issues before and after
    CI adoption, segmented by project size.
    """
    parser = argparse.ArgumentParser(description="Generate plots for bug issues by project size.")
    parser.add_argument(
        "--bugs-file",
        required=True,
        help="Path to the bug counts CSV file (from 31_ci_bug_issues_count.py).",
    )
    parser.add_argument(
        "--sizes-file",
        required=True,
        help="Path to the repo summary CSV file with SLOC (from 29_ci_theater_polyglot_rust.py).",
    )
    parser.add_argument(
        "--output-scatter-plot", required=True, help="Path to save the bug ratio vs SLOC scatter plot."
    )
    parser.add_argument(
        "--output-boxplot", required=True, help="Path to save the bug ratio by size boxplot."
    )
    parser.add_argument(
        "--output-comparison-boxplot", required=True, help="Path to save the before vs. after bug counts boxplot."
    )
    parser.add_argument(
        "--cohort-name",
        required=True,
        help="Name of the cohort for plot titles (e.g., 'Monoglot' or 'Polyglot').",
    )
    args = parser.parse_args()

    # Load data
    try:
        bugs_df = pd.read_csv(args.bugs_file)
        sizes_df = pd.read_csv(args.sizes_file)
    except FileNotFoundError as e:
        print(f"Error: Missing required CSV file: {e.filename}")
        print("Please run the prerequisite scripts first.")
        return

    # --- Plot 0: Raw Before vs After Boxplot (replaces script 26) ---
    plt.figure(figsize=(8, 6))
    bugs_df[["Bug Issues Before CI", "Bug Issues After CI"]].plot.box()
    plt.title(f"Bug-Like Issues Before vs. After CI Adoption ({args.cohort_name} Projects)")
    plt.ylabel("Number of Inferred Bug Issues")

    # Cap the y-axis to make the box plots more readable, avoiding extreme outliers
    if not bugs_df.empty:
        # Use the 95th percentile of all bug counts as a reasonable upper limit
        q95 = bugs_df[["Bug Issues Before CI", "Bug Issues After CI"]].stack().quantile(0.95)
        plt.ylim(0, q95 * 1.2)  # Cap at 95th percentile + 20% buffer

    plt.grid(True)
    plt.tight_layout()

    out_path0 = args.output_comparison_boxplot
    os.makedirs(os.path.dirname(out_path0) or ".", exist_ok=True)
    plt.savefig(out_path0, dpi=300, bbox_inches='tight')
    print(f"✅ Before-vs-after boxplot saved to {out_path0}")
    plt.close()

    # Merge datasets
    sizes_df["Category"] = sizes_df["rust_sloc"].apply(categorize_project)
    df = pd.merge(bugs_df, sizes_df, left_on="Project", right_on="repo", how="inner")

    # --- Feature Engineering & Cleaning ---
    # To avoid division by zero and to smooth the ratio for small numbers,
    # we add 1 to both the numerator and denominator (Laplace smoothing).
    # A ratio > 1.0 means more bugs were reported per unit of time after CI.
    # A ratio < 1.0 means fewer bugs were reported.
    df["Bug_Ratio"] = (df["Bug Issues After CI"] + 1) / (df["Bug Issues Before CI"] + 1)

    # Ensure SLOC is numeric for plotting
    df["rust_sloc"] = pd.to_numeric(df["rust_sloc"], errors="coerce")
    df.dropna(subset=["rust_sloc", "Bug_Ratio"], inplace=True)

    if df.empty:
        print("No valid data to plot after merging and cleaning. Exiting.")
        return

    # Define the order of categories for plotting
    category_order = ["Very Small", "Small", "Medium", "Large", "Very Large"]
    df['Category'] = pd.Categorical(df['Category'], categories=category_order, ordered=True)
    df.sort_values('Category', inplace=True)

    # --- Plot 1: Scatter Plot (Bug Ratio vs. Project Size) ---
    plt.figure(figsize=(12, 7))
    sns.scatterplot(
        data=df,
        x="rust_sloc",
        y="Bug_Ratio",
        hue="Category",
        hue_order=category_order,
        alpha=0.7,
        s=50 # marker size
    )
    plt.xscale("log")
    plt.axhline(y=1.0, color='red', linestyle='--', label='No Change (Ratio = 1.0)')
    plt.title(f"Change in Bug Reports After CI Adoption vs. Project Size ({args.cohort_name} Projects)")
    plt.xlabel("Project Size (Rust SLOC, log scale)")
    plt.ylabel("Bug Ratio (After CI / Before CI)")
    plt.legend(title="Project Size")
    plt.grid(True, which="both", ls="--", c='0.7')
    plt.tight_layout()

    out_path1 = args.output_scatter_plot
    os.makedirs(os.path.dirname(out_path1) or ".", exist_ok=True)
    plt.savefig(out_path1, dpi=300, bbox_inches='tight')
    print(f"✅ Scatter plot saved to {out_path1}")
    plt.close()

    # --- Plot 2: Box Plot (Bug Ratio by Category) ---
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x="Category", y="Bug_Ratio", order=category_order)
    plt.axhline(y=1.0, color='red', linestyle='--', label='No Change (Ratio = 1.0)')
    plt.title(f"Distribution of Bug Report Ratio by Project Size Category ({args.cohort_name} Projects)")
    plt.xlabel("Project Size Category")
    plt.ylabel("Bug Ratio (After CI / Before CI)")
    # Cap the y-axis to make the box plots more readable, as ratios can be very high
    if not df["Bug_Ratio"].empty:
        plt.ylim(0, df["Bug_Ratio"].quantile(0.95) * 1.1)
    plt.legend()
    plt.grid(True, axis='y')
    plt.tight_layout()

    out_path2 = args.output_boxplot
    os.makedirs(os.path.dirname(out_path2) or ".", exist_ok=True)
    plt.savefig(out_path2, dpi=300, bbox_inches='tight')
    print(f"✅ Box plot saved to {out_path2}")
    plt.close()

if __name__ == "__main__":
    main()