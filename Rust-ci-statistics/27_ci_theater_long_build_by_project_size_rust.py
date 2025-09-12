import argparse
import os

import pandas as pd
import matplotlib.pyplot as plt
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


def main():
    parser = argparse.ArgumentParser(
        description="Generate a boxplot of average build duration by project size for a specific cohort."
    )
    parser.add_argument(
        "--builds-file",
        required=True,
        help="Path to the long builds CSV file (e.g., from 22_ci_theater_long_builds_rust.py).",
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
    parser.add_argument(
        "--plot-style",
        default="default",
        choices=['default', 'log', 'no-outliers', 'dual-panel', 'violin', 'broken-axis'],
        help="The style of plot to generate for visualizing outliers and long tails."
    )
    args = parser.parse_args()

    try:
        builds_df = pd.read_csv(args.builds_file)
        sizes_df = pd.read_csv(args.sizes_file)
    except FileNotFoundError as e:
        print(f"Error: Input file not found: {e.filename}")
        print("Please ensure you have run the prerequisite scripts for both builds and sizes.")
        return

    sizes_df["Category"] = sizes_df["rust_sloc"].apply(categorize_project)
    df = pd.merge(builds_df, sizes_df[["repo", "Category"]], left_on="name", right_on="repo", how="inner")

    df["Avg Duration (min)"] = pd.to_numeric(df["Avg Duration (min)"], errors="coerce")
    df["Runs Counted"] = pd.to_numeric(df["Runs Counted"], errors="coerce")
    df = df[df["Runs Counted"] > 0]
    df.dropna(subset=["Avg Duration (min)"], inplace=True)

    if df.empty:
        print("\nError: No valid data to plot after merging and cleaning.")
        return

    # --- Analysis & Reporting ---
    print(f"\n--- Build Duration Analysis for {args.cohort_name} Cohort ---")

    # Calculate percentiles on the "Avg Duration (min)" for all projects in the cohort
    p95 = df["Avg Duration (min)"].quantile(0.95)
    p_max = df["Avg Duration (min)"].max()

    print(f"95% of projects have an average build duration of {p95:.2f} minutes or less.")
    print(f"The remaining 5% of projects have average build durations up to {p_max:.2f} minutes.")

    # Separate into typical and exceptional groups
    typical_builds_df = df[df["Avg Duration (min)"] <= p95]
    exceptional_builds_df = df[df["Avg Duration (min)"] > p95]

    print("\n--- Statistics for 'Typical' Projects (<= 95th percentile) ---")
    print(f"Number of projects: {len(typical_builds_df)}")
    print(typical_builds_df["Avg Duration (min)"].describe())

    print("\n--- Statistics for 'Exceptional' Projects (> 95th percentile) ---")
    print(f"Number of projects: {len(exceptional_builds_df)}")
    if not exceptional_builds_df.empty:
        print(exceptional_builds_df["Avg Duration (min)"].describe())
    else:
        print("No exceptional builds found (>95th percentile).")
    print("-" * 50 + "\n")

    valid_data = df[df["Avg Duration (min)"].notna()]
    median = valid_data["Avg Duration (min)"].median()
    q3 = valid_data["Avg Duration (min)"].quantile(0.75)
    p95_plot = valid_data["Avg Duration (min)"].quantile(0.95)

    category_order = ["Very Small", "Small", "Medium", "Large", "Very Large"]
    df['Category'] = pd.Categorical(df['Category'], categories=category_order, ordered=True)
    df.sort_values('Category', inplace=True)

    # --- Plotting ---
    # Common elements for many plots
    h_lines = [
        (10, 'red', '--', "10-minute Threshold"),
        (median, 'green', '--', f"Median ({median:.2f} min)"),
        (q3, 'orange', '--', f"75th Percentile ({q3:.2f} min)"),
        (p95_plot, 'purple', ':', f"95th Percentile ({p95_plot:.2f} min)")
    ]

    if args.plot_style == 'default':
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.boxplot(ax=ax, data=df, x="Category", y="Avg Duration (min)", order=category_order)
        for y, color, style, label in h_lines:
            ax.axhline(y=y, color=color, linestyle=style, label=label)
        ax.set_title(f"Average Build Duration by Project Size ({args.cohort_name} Projects)")
        ax.set_xlabel("Project Size Category")
        ax.set_ylabel("Avg Build Duration (minutes)")
        ax.tick_params(axis='x', rotation=10)
        ax.legend()
        ax.grid(True, axis='y')
        plt.tight_layout()

    elif args.plot_style == 'log':
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.boxplot(ax=ax, data=df, x="Category", y="Avg Duration (min)", order=category_order)
        for y, color, style, label in h_lines:
            ax.axhline(y=y, color=color, linestyle=style, label=label)
        ax.set_yscale('log')
        ax.set_title(f"Average Build Duration by Project Size (Log Scale) ({args.cohort_name} Projects)")
        ax.set_xlabel("Project Size Category")
        ax.set_ylabel("Avg Build Duration (minutes, log scale)")
        ax.tick_params(axis='x', rotation=10)
        ax.legend()
        ax.grid(True, which="both", ls="--", c='0.7')
        plt.tight_layout()

    elif args.plot_style == 'no-outliers':
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.boxplot(ax=ax, data=df, x="Category", y="Avg Duration (min)", order=category_order, showfliers=False)
        ax.set_title(f"Build Duration (Outliers Suppressed) by Project Size ({args.cohort_name} Projects)")
        ax.set_xlabel("Project Size Category")
        ax.set_ylabel("Avg Build Duration (minutes)")
        ax.tick_params(axis='x', rotation=10)
        ax.grid(True, axis='y')
        max_val = df["Avg Duration (min)"].max()
        ax.text(0.98, 0.98, f"Max: {max_val:.2f} min\n95th: {p95_plot:.2f} min",
                transform=ax.transAxes, fontsize=12,
                verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        plt.tight_layout()

    elif args.plot_style == 'violin':
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.violinplot(ax=ax, data=df, x="Category", y="Avg Duration (min)", order=category_order, inner="box")
        for y, color, style, label in h_lines:
            ax.axhline(y=y, color=color, linestyle=style, label=label)
        ax.set_title(f"Build Duration Distribution by Project Size ({args.cohort_name} Projects)")
        ax.set_xlabel("Project Size Category")
        ax.set_ylabel("Avg Build Duration (minutes)")
        ax.tick_params(axis='x', rotation=10)
        ax.legend()
        ax.grid(True, axis='y')
        plt.tight_layout()

    elif args.plot_style == 'dual-panel':
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7), sharey=False)
        fig.suptitle(f"Average Build Duration by Project Size ({args.cohort_name} Projects)", fontsize=16)

        # Panel A: Zoomed
        sns.boxplot(ax=ax1, data=df, x="Category", y="Avg Duration (min)", order=category_order)
        ax1.set_ylim(0, 20)
        ax1.set_title("Typical Builds (0-20 minutes)")
        ax1.set_xlabel("Project Size Category")
        ax1.set_ylabel("Avg Build Duration (minutes)")
        ax1.tick_params(axis='x', rotation=15)
        ax1.grid(True, axis='y')

        # Panel B: Full Range
        sns.boxplot(ax=ax2, data=df, x="Category", y="Avg Duration (min)", order=category_order)
        ax2.set_title("Full Range (including outliers)")
        ax2.set_xlabel("Project Size Category")
        ax2.set_ylabel("")
        ax2.tick_params(axis='x', rotation=15)
        ax2.grid(True, axis='y')

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    elif args.plot_style == 'broken-axis':
        y_break_low = 25
        y_break_high = 40

        fig, (ax_top, ax_bottom) = plt.subplots(2, 1, sharex=True, figsize=(12, 8), gridspec_kw={'height_ratios': [1, 2]})
        fig.suptitle(f"Average Build Duration by Project Size ({args.cohort_name} Projects)", fontsize=16)

        sns.boxplot(ax=ax_top, data=df, x="Category", y="Avg Duration (min)", order=category_order)
        sns.boxplot(ax=ax_bottom, data=df, x="Category", y="Avg Duration (min)", order=category_order)

        max_val = df["Avg Duration (min)"].max()
        ax_top.set_ylim(bottom=y_break_high, top=max_val * 1.05)
        ax_bottom.set_ylim(bottom=0, top=y_break_low)

        ax_top.spines['bottom'].set_visible(False)
        ax_bottom.spines['top'].set_visible(False)
        ax_top.xaxis.tick_top()
        ax_top.tick_params(labeltop=False)
        ax_bottom.xaxis.tick_bottom()

        d = .015
        kwargs = dict(transform=ax_top.transAxes, color='k', clip_on=False)
        ax_top.plot((-d, +d), (-d, +d), **kwargs)
        ax_top.plot((1 - d, 1 + d), (-d, +d), **kwargs)
        kwargs.update(transform=ax_bottom.transAxes)
        ax_bottom.plot((-d, +d), (1 - d, 1 + d), **kwargs)
        ax_bottom.plot((1 - d, 1 + d), (1 - d, 1 + d), **kwargs)

        fig.text(0.06, 0.5, 'Avg Build Duration (minutes)', va='center', rotation='vertical')
        ax_bottom.set_xlabel("Project Size Category")
        ax_top.set_xlabel("")
        ax_top.set_ylabel("")
        ax_bottom.set_ylabel("")
        ax_bottom.tick_params(axis='x', rotation=10)

        for y, color, style, label in h_lines:
            if y <= y_break_low:
                ax_bottom.axhline(y=y, color=color, linestyle=style, label=label)
            if y >= y_break_high:
                ax_top.axhline(y=y, color=color, linestyle=style, label=label)

        ax_bottom.legend(loc='upper left')
        ax_top.legend(loc='upper left')
        plt.subplots_adjust(hspace=0.05)

    os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
    plt.savefig(args.output_file, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to {args.output_file}")


if __name__ == "__main__":
    main()
