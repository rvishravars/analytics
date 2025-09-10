#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# --- Config ---
BUG_COUNTS_CSV = "data/31_bug_issues_before_after_ci.csv"
PROJECT_SIZES_CSV = "data/19_ci_theater_project_sizes_rust.csv"
OUTPUT_DIR = "data"

def main():
    """
    Generates plots comparing the change in bug-like issues before and after
    CI adoption, segmented by project size.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load data
    try:
        bugs_df = pd.read_csv(BUG_COUNTS_CSV)
        sizes_df = pd.read_csv(PROJECT_SIZES_CSV)
    except FileNotFoundError as e:
        print(f"Error: Missing required CSV file: {e.filename}")
        print("Please run '31_ci_bug_issues_count.py' and '19_ci_theater_project_size_rust.py' first.")
        return

    # Merge datasets
    df = pd.merge(bugs_df, sizes_df, left_on="Project", right_on="name", how="inner")

    # --- Feature Engineering & Cleaning ---
    # To avoid division by zero and to smooth the ratio for small numbers,
    # we add 1 to both the numerator and denominator (Laplace smoothing).
    # A ratio > 1.0 means more bugs were reported per unit of time after CI.
    # A ratio < 1.0 means fewer bugs were reported.
    df["Bug_Ratio"] = (df["Bug Issues After CI"] + 1) / (df["Bug Issues Before CI"] + 1)

    # Ensure SLOC is numeric for plotting
    df["SLOC"] = pd.to_numeric(df["SLOC"], errors="coerce")
    df.dropna(subset=["SLOC", "Bug_Ratio"], inplace=True)

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
        x="SLOC",
        y="Bug_Ratio",
        hue="Category",
        hue_order=category_order,
        alpha=0.7,
        s=50 # marker size
    )
    plt.xscale("log")
    plt.axhline(y=1.0, color='red', linestyle='--', label='No Change (Ratio = 1.0)')
    plt.title("Change in Bug Reports After CI Adoption vs. Project Size")
    plt.xlabel("Project Size (SLOC, log scale)")
    plt.ylabel("Bug Ratio (After CI / Before CI)")
    plt.legend(title="Project Size")
    plt.grid(True, which="both", ls="--", c='0.7')
    plt.tight_layout()

    out_path1 = os.path.join(OUTPUT_DIR, "31_1_bug_ratio_vs_sloc_rust.png")
    plt.savefig(out_path1, dpi=300, bbox_inches='tight')
    print(f"✅ Scatter plot saved to {out_path1}")
    plt.close()

    # --- Plot 2: Box Plot (Bug Ratio by Category) ---
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x="Category", y="Bug_Ratio", order=category_order)
    plt.axhline(y=1.0, color='red', linestyle='--', label='No Change (Ratio = 1.0)')
    plt.title("Distribution of Bug Report Ratio by Project Size Category")
    plt.xlabel("Project Size Category")
    plt.ylabel("Bug Ratio (After CI / Before CI)")
    # Cap the y-axis to make the box plots more readable, as ratios can be very high
    plt.ylim(0, df["Bug_Ratio"].quantile(0.95) * 1.1)
    plt.legend()
    plt.grid(True, axis='y')
    plt.tight_layout()

    out_path2 = os.path.join(OUTPUT_DIR, "31_1_bug_ratio_by_size_boxplot_rust.png")
    plt.savefig(out_path2, dpi=300, bbox_inches='tight')
    print(f"✅ Box plot saved to {out_path2}")
    plt.close()

if __name__ == "__main__":
    main()