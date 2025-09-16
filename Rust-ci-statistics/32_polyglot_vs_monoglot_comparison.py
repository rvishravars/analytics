#!/usr/bin/env python3
"""
Compares CI health metrics between monoglot and polyglot Rust projects.

This script loads the output CSVs from other analyses (which should be run
separately for monoglot and polyglot project lists) and generates
comparative plots.
"""
import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def load_and_combine(metric_prefix: str, monoglot_csv: str, polyglot_csv: str) -> pd.DataFrame:
    """Loads and concatenates monoglot and polyglot data, adding a 'group' column."""
    try:
        mono_df = pd.read_csv(monoglot_csv)
        poly_df = pd.read_csv(polyglot_csv)
        mono_df['group'] = 'Monoglot'
        poly_df['group'] = 'Polyglot'
        return pd.concat([mono_df, poly_df], ignore_index=True)
    except FileNotFoundError as e:
        print(f"Skipping {metric_prefix}: Missing file {e.filename}")
        return pd.DataFrame()

def compare_metric(df: pd.DataFrame, metric_column: str, title: str, ylabel: str, out_name: str, output_dir: str, log_scale: bool = False, summary_text: str = None):
    """Generates a boxplot and summary statistics for a given metric."""
    if df.empty or metric_column not in df.columns:
        return

    df[metric_column] = pd.to_numeric(df[metric_column], errors='coerce')
    df.dropna(subset=[metric_column], inplace=True)

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.boxplot(ax=ax, data=df, x='group', y=metric_column, order=['Monoglot', 'Polyglot'], boxprops=dict(facecolor='white'))

    if log_scale:
        ax.set_yscale('log')
        ylabel += " (log scale)"
        ax.grid(True, which="both", ls="--", c='0.7')
    else:
        ax.grid(True, axis='y')
        # Apply y-axis cap for build duration plot
        if metric_column == "Avg Duration (min)":
            ax.set_ylim(0, 60)

    ax.set_title(title)
    ax.set_xlabel("Project Type")
    ax.set_ylabel(ylabel)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(os.path.join(output_dir, f"{out_name}.png"), dpi=300)
    plt.close()
    print(f"✅ Plot saved to {output_dir}/{out_name}.png")

    # --- Summary Statistics ---
    print(f"\n--- Summary Statistics for '{title}' ---")
    summary_df = df.groupby('group')[metric_column].describe()
    print(summary_df.to_string())

    # Save summary to CSV
    summary_csv_path = os.path.join(output_dir, f"{out_name}_stats.csv")
    summary_df.to_csv(summary_csv_path)
    print(f"✅ Statistics saved to {summary_csv_path}\n")

def main():
    parser = argparse.ArgumentParser(description="Compare monoglot and polyglot project metrics.")
    parser.add_argument(
        "--output-dir", default="figures/polyglot_comparison", help="Directory to save output figures."
    )

    # Commit Frequency
    parser.add_argument(
        "--commit-freq-mono", default="data/20_commit_freq_monoglot.csv", help="Path to monoglot commit frequency CSV."
    )
    parser.add_argument(
        "--commit-freq-poly", default="data/20_commit_freq_polyglot.csv", help="Path to polyglot commit frequency CSV."
    )

    # Build Duration
    parser.add_argument(
        "--build-duration-mono", default="data/22_long_builds_monoglot.csv", help="Path to monoglot build duration CSV."
    )
    parser.add_argument(
        "--build-duration-poly", default="data/22_long_builds_polyglot.csv", help="Path to polyglot build duration CSV."
    )

    # Test Coverage
    parser.add_argument(
        "--coverage-mono", default="data/24_coverage_monoglot.csv", help="Path to monoglot test coverage CSV."
    )
    parser.add_argument(
        "--coverage-poly", default="data/24_coverage_polyglot.csv", help="Path to polyglot test coverage CSV."
    )

    # Broken Builds
    parser.add_argument(
        "--broken-builds-mono", default="data/28_broken_builds_monoglot.csv", help="Path to monoglot broken builds CSV."
    )
    parser.add_argument(
        "--broken-builds-poly", default="data/28_broken_builds_polyglot.csv", help="Path to polyglot broken builds CSV."
    )

    # Bug Issues
    parser.add_argument("--bugs-mono", default="data/31_bugs_monoglot.csv", help="Path to monoglot bug issues CSV.")
    parser.add_argument("--bugs-poly", default="data/31_bugs_polyglot.csv", help="Path to polyglot bug issues CSV.")

    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Compare commit frequency
    commit_df = load_and_combine("Commit Frequency", args.commit_freq_mono, args.commit_freq_poly)
    if not commit_df.empty:
        # Handle multiple possible column names for commit frequency
        commit_col_new = "Avg_Commits_Weekday"
        commit_col_legacy = "Avg Commits/Weekday (Mon–Fri)"
        commit_col_malformed = "Weekday (Mon–Fri)"  # From malformed CSVs

        if commit_col_new in commit_df.columns:
            commit_col = commit_col_new
        elif commit_col_legacy in commit_df.columns:
            commit_col = commit_col_legacy
        elif commit_col_malformed in commit_df.columns:
            commit_col = commit_col_malformed
        else:
            commit_col = None

        compare_metric(commit_df, commit_col, "Commit Frequency: Monoglot vs. Polyglot", "Avg. Commits / Weekday", "commit_freq_comparison", args.output_dir)

    # Compare build durations
    build_df = load_and_combine("Build Duration", args.build_duration_mono, args.build_duration_poly)
    build_summary_text = None
    if not build_df.empty:
        numeric_build_durations = pd.to_numeric(build_df["Avg Duration (min)"], errors="coerce").dropna()
        if not numeric_build_durations.empty:
            median = numeric_build_durations.median()
            q3 = numeric_build_durations.quantile(0.75)
            p95 = numeric_build_durations.quantile(0.95)
            build_summary_text = f"Overall Median: {median:.2f}\nOverall 75th: {q3:.2f}\nOverall 95th: {p95:.2f}"

    compare_metric(build_df, "Avg Duration (min)", "Build Duration: Monoglot vs. Polyglot",
                   "Avg. Duration (min)", "build_duration_comparison", args.output_dir,
                   log_scale=False, summary_text=build_summary_text)

    # Compare test coverage
    coverage_df = load_and_combine("Test Coverage", args.coverage_mono, args.coverage_poly)
    compare_metric(coverage_df, "Coverage Latest (%)", "Test Coverage: Monoglot vs. Polyglot", "Latest Coverage (%)", "coverage_comparison", args.output_dir)

    # Compare broken build metrics
    broken_df = load_and_combine("Broken Builds", args.broken_builds_mono, args.broken_builds_poly)
    compare_metric(broken_df, "Max Broken Days", "Max Broken Build Duration: Monoglot vs. Polyglot", "Max Days Broken", "max_broken_days_comparison", args.output_dir)
    compare_metric(broken_df, "Broken >2 Days", "Long Broken Build Stretches (>2 Days): Monoglot vs. Polyglot", "Count of Stretches > 2 Days", "long_broken_stretches_comparison", args.output_dir)

    # Compare bug-like issues
    bugs_df = load_and_combine("Bug Issues", args.bugs_mono, args.bugs_poly)
    # To compare fairly, we'll look at the ratio of bugs after vs before CI
    if not bugs_df.empty:
        bugs_df["Bug_Ratio"] = (bugs_df["Bug Issues After CI"] + 1) / (bugs_df["Bug Issues Before CI"] + 1)
        compare_metric(bugs_df, "Bug_Ratio", "Bug Report Ratio (Post-CI / Pre-CI): Monoglot vs. Polyglot", "Bug Ratio", "bug_ratio_comparison", args.output_dir)

if __name__ == "__main__":
    main()