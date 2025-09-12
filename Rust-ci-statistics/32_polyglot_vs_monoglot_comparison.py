#!/usr/bin/env python3
"""
Compares CI health metrics between monoglot and polyglot Rust projects.

This script loads the output CSVs from other analyses (which should be run
separately for monoglot and polyglot project lists) and generates
comparative plots and statistical tests.
"""
import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import mannwhitneyu

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

def compare_metric(df: pd.DataFrame, metric_column: str, title: str, ylabel: str, out_name: str, output_dir: str):
    """Generates a boxplot and runs a Mann-Whitney U test for a given metric."""
    if df.empty or metric_column not in df.columns:
        return

    df[metric_column] = pd.to_numeric(df[metric_column], errors='coerce')
    df.dropna(subset=[metric_column], inplace=True)

    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x='group', y=metric_column, order=['Monoglot', 'Polyglot'])
    plt.title(title)
    plt.xlabel("Project Type")
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{out_name}.png"), dpi=300)
    plt.close()
    print(f"✅ Plot saved to {output_dir}/{out_name}.png")

    # Statistical significance test
    mono_data = df[df['group'] == 'Monoglot'][metric_column].dropna()
    poly_data = df[df['group'] == 'Polyglot'][metric_column].dropna()

    if not mono_data.empty and not poly_data.empty:
        stat, p_value = mannwhitneyu(mono_data, poly_data, alternative='two-sided')
        print(f"  - Mann-Whitney U test for '{metric_column}': p-value = {p_value:.4f}")
        if p_value < 0.05:
            print("    -> Statistically significant difference found.")
        else:
            print("    -> No statistically significant difference.")

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
    compare_metric(commit_df, "Avg Commits/Weekday (Mon–Fri)", "Commit Frequency: Monoglot vs. Polyglot", "Avg. Commits / Weekday", "commit_freq_comparison", args.output_dir)

    # Compare build durations
    build_df = load_and_combine("Build Duration", args.build_duration_mono, args.build_duration_poly)
    compare_metric(build_df, "Avg Duration (min)", "Build Duration: Monoglot vs. Polyglot", "Avg. Duration (min)", "build_duration_comparison", args.output_dir)

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