import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def categorize_project(sloc: int) -> str:
    """Categorizes a project based on its source lines of code (SLOC)."""
    if sloc < 10000:
        return "Small"
    elif sloc < 100000:
        return "Medium"
    else:
        return "Large"

def process_cohort(builds_file: str, sizes_file: str, cohort_name: str):
    """
    Reads build and size data, merges them, and prepares a DataFrame for plotting.
    """
    try:
        builds_df = pd.read_csv(builds_file)
        sizes_df = pd.read_csv(sizes_file)
    except FileNotFoundError as e:
        print(f"Error: Input file not found: {e.filename}")
        return None

    # Prepare and merge dataframes
    sizes_df["Category"] = sizes_df["rust_sloc"].apply(categorize_project)
    df = pd.merge(builds_df, sizes_df[["repo", "Category"]], left_on="name", right_on="repo", how="inner")
    
    # Clean and process data
    df["Avg Duration (min)"] = pd.to_numeric(df["Avg Duration (min)"], errors="coerce")
    df["Runs Counted"] = pd.to_numeric(df["Runs Counted"], errors="coerce")
    df = df[df["Runs Counted"] > 0]
    df.dropna(subset=["Avg Duration (min)"], inplace=True)
    
    if df.empty:
        print(f"\nError: No valid data to plot for {cohort_name}.")
        return None

    # Calculate overall statistics
    median = df["Avg Duration (min)"].median()
    
    # Set up categories for consistent plotting order
    all_categories = ["Small", "Medium", "Large"]
    category_order = [cat for cat in all_categories if cat in df['Category'].unique()]
    df['Category'] = pd.Categorical(df['Category'], categories=category_order, ordered=True)
    df.sort_values('Category', inplace=True)
    
    return df, category_order, median


def composite_plot(mono_args, poly_args, output_file: str, plot_style: str):
    """
    Generates and saves a composite plot comparing build durations for two cohorts.
    """
    mono_data = process_cohort(mono_args["builds_file"], mono_args["sizes_file"], "Monoglot")
    poly_data = process_cohort(poly_args["builds_file"], poly_args["sizes_file"], "Polyglot")
    
    if mono_data is None or poly_data is None:
        print("Failed to process one or more cohorts. Exiting.")
        return

    df_mono, cat_order_mono, median_mono = mono_data
    df_poly, cat_order_poly, median_poly = poly_data

    # --- Print summary info for Monoglot ---
    print(f"\n--- Build Duration Analysis for Monoglot Cohort ---")
    print(f"Overall Median: {median_mono:.2f} min")
    # The 75th percentile (third quartile) is crucial for defining the top of the box in the boxplot.
    group_stats_mono = df_mono.groupby('Category')["Avg Duration (min)"].agg(
        mean="mean",
        median="median",
        first_quartile=lambda x: x.quantile(0.25),
        seventy_fifth_percentile=lambda x: x.quantile(0.75) # Use a valid identifier
    ).rename(columns={"seventy_fifth_percentile": "75th_Percentile"}) # Rename for display
    print("Monoglot stats by category:")
    print(group_stats_mono.to_string())

    # --- Print summary info for Polyglot ---
    print(f"\n--- Build Duration Analysis for Polyglot Cohort ---")
    print(f"Overall Median: {median_poly:.2f} min")
    # Any data point above 1.5 * IQR + 75th_Percentile is considered an outlier.
    group_stats_poly = df_poly.groupby('Category')["Avg Duration (min)"].agg(
        mean="mean",
        median="median",
        first_quartile=lambda x: x.quantile(0.25),
        seventy_fifth_percentile=lambda x: x.quantile(0.75) # Use a valid identifier
    ).rename(columns={"seventy_fifth_percentile": "75th_Percentile"}) # Rename for display
    print("Polyglot stats by category:")
    print(group_stats_poly.to_string())

    # Create a figure with two subplots for box plots
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))

    # --- Monoglot subplot ---
    ax = axes[0]
    sns.boxplot(
        ax=ax, 
        data=df_mono, 
        x="Category", 
        y="Avg Duration (min)", 
        order=cat_order_mono, 
        showfliers=True,
        boxprops=dict(facecolor='white')
    )
    ax.set_title("Average Build Duration (Monoglot Projects)")
    ax.set_xlabel("Project Size Category")
    ax.set_ylabel("Avg Build Duration (minutes)")
    ax.tick_params(axis='x', rotation=10)
    ax.grid(True, axis='y')
    if plot_style == "log":
        ax.set_yscale('log')
    else:
        ax.set_ylim(bottom=0) # Adjust ylim to start at 0
    
    # --- Polyglot subplot ---
    ax2 = axes[1]
    sns.boxplot(
        ax=ax2, 
        data=df_poly, 
        x="Category", 
        y="Avg Duration (min)", 
        order=cat_order_poly, 
        showfliers=True,
        boxprops=dict(facecolor='white')
    )
    ax2.set_title("Average Build Duration (Polyglot Projects)")
    ax2.set_xlabel("Project Size Category")
    ax2.set_ylabel("Avg Build Duration (minutes)")
    ax2.tick_params(axis='x', rotation=10)
    ax2.grid(True, axis='y')
    if plot_style == "log":
        ax2.set_yscale('log')
    else:
        ax2.set_ylim(bottom=0) # Adjust ylim to start at 0
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\n✅ Combined plot saved to {output_file}")


def main():
    """Parses command-line arguments and runs the plotting function."""
    parser = argparse.ArgumentParser(
        description="Generate a combined average build duration plot for both Monoglot and Polyglot cohorts."
    )
    parser.add_argument("--mono-builds-file", required=True, help="Path to the monoglot long builds CSV file.")
    parser.add_argument("--mono-sizes-file", required=True, help="Path to the monoglot repo summary CSV file with SLOC.")
    parser.add_argument("--poly-builds-file", required=True, help="Path to the polyglot long builds CSV file.")
    parser.add_argument("--poly-sizes-file", required=True, help="Path to the polyglot repo summary CSV file with SLOC.")
    parser.add_argument("--output-file", required=True, help="Path to save the combined output plot PNG file.")
    parser.add_argument("--plot-style", default="default", choices=['default', 'log'],
                        help="Plot style for visualizing build durations (composite supports default and log).")
    args = parser.parse_args()

    mono_args = {
        "builds_file": args.mono_builds_file,
        "sizes_file": args.mono_sizes_file
    }
    poly_args = {
        "builds_file": args.poly_builds_file,
        "sizes_file": args.poly_sizes_file
    }
    composite_plot(mono_args, poly_args, args.output_file, args.plot_style)

if __name__ == "__main__":
    main()

