#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt

# --- Config ---
BROKEN_BUILDS_CSV = "data/28_ci_theater_broken_builds_rust.csv"
PROJECT_SIZES_CSV = "data/19_ci_theater_project_sizes_rust.csv"
OUTPUT_DIR = "data"

# --- Main ---
def main():
    """
    Generates box plots comparing CI build brokenness metrics against project size.
    """
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load data
    try:
        broken_builds_df = pd.read_csv(BROKEN_BUILDS_CSV)
        project_sizes_df = pd.read_csv(PROJECT_SIZES_CSV)
    except FileNotFoundError as e:
        print(f"Error: Missing required CSV file: {e.filename}")
        print("Please run '28_ci_theater_broken_builds_rust.py' and '19_ci_theater_project_size_rust.py' first.")
        return

    # Merge on project name
    df = pd.merge(broken_builds_df, project_sizes_df[["name", "Category"]], on="name", how="inner")

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
    df.boxplot(column="Broken >2 Days", by="Category", grid=True)

    median_val = df["Broken >2 Days"].median()
    plt.axhline(y=median_val, color='green', linestyle='--', label=f"Overall Median ({median_val:.2f})")

    plt.title("Count of Long Broken Build Stretches (>2 Days) by Project Size")
    plt.suptitle("")
    plt.xlabel("Project Size Category")
    plt.ylabel("Number of Stretches > 2 Days")
    plt.xticks(rotation=10)
    plt.legend()
    plt.tight_layout()

    out_path1 = os.path.join(OUTPUT_DIR, "28_1_broken_stretches_by_size_rust.png")
    plt.savefig(out_path1, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to {out_path1}")
    plt.close()

    # --- Plot 2: Maximum duration of a broken build stretch ---
    plt.figure(figsize=(10, 6))
    df.boxplot(column="Max Broken Days", by="Category", grid=True)

    plt.title("Maximum Broken Build Duration by Project Size")
    plt.suptitle("")
    plt.xlabel("Project Size Category")
    plt.ylabel("Max Days Build Remained Broken")
    plt.xticks(rotation=10)
    plt.tight_layout()

    out_path2 = os.path.join(OUTPUT_DIR, "28_1_max_broken_days_by_size_rust.png")
    plt.savefig(out_path2, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to {out_path2}")
    plt.close()

if __name__ == "__main__":
    main()