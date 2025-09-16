#!/usr/bin/env python3
import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def create_ci_adoption_graph(mono_csv, poly_csv, mono_total_csv, poly_total_csv, output_file):
    try:
        mono_df = pd.read_csv(mono_csv)
        poly_df = pd.read_csv(poly_csv)
        mono_total_df = pd.read_csv(mono_total_csv)
        poly_total_df = pd.read_csv(poly_total_csv)
    except FileNotFoundError as e:
        print(f"Error: Input file not found: {e.filename}")
        return

    total_mono = len(mono_total_df)
    total_poly = len(poly_total_df)

    # Convert Coverage Samples to numeric
    mono_df['Coverage Samples'] = pd.to_numeric(mono_df['Coverage Samples'], errors='coerce').fillna(0)
    poly_df['Coverage Samples'] = pd.to_numeric(poly_df['Coverage Samples'], errors='coerce').fillna(0)

    # CI test configured
    mono_with_ci = mono_df[mono_df['Tests in CI (configured)'] == 'Yes']
    poly_with_ci = poly_df[poly_df['Tests in CI (configured)'] == 'Yes']

    # CI coverage configured AND samples > 0
    mono_with_coverage = mono_with_ci[
        (mono_with_ci['Coverage in CI (configured)'] == 'Yes') &
        (mono_with_ci['Coverage Samples'] > 0)
    ]
    poly_with_coverage = poly_with_ci[
        (poly_with_ci['Coverage in CI (configured)'] == 'Yes') &
        (poly_with_ci['Coverage Samples'] > 0)
    ]

    # Counts
    with_coverage_mono = len(mono_with_coverage)
    with_coverage_poly = len(poly_with_coverage)
    with_tests_only_mono = len(mono_with_ci) - with_coverage_mono
    with_tests_only_poly = len(poly_with_ci) - with_coverage_poly
    without_tests_mono = total_mono - len(mono_with_ci)
    without_tests_poly = total_poly - len(poly_with_ci)

    # Plot data
    plot_data = pd.DataFrame([
        {'Cohort': 'Monoglot', 'Category': 'With CI Tests & Coverage', 'Count': with_coverage_mono},
        {'Cohort': 'Monoglot', 'Category': 'With CI Tests Only', 'Count': with_tests_only_mono},
        {'Cohort': 'Monoglot', 'Category': 'Without CI Tests', 'Count': without_tests_mono},
        {'Cohort': 'Polyglot', 'Category': 'With CI Tests & Coverage', 'Count': with_coverage_poly},
        {'Cohort': 'Polyglot', 'Category': 'With CI Tests Only', 'Count': with_tests_only_poly},
        {'Cohort': 'Polyglot', 'Category': 'Without CI Tests', 'Count': without_tests_poly},
    ])

    # Plot
    blue_shades = ["#08519c", "#6baed6", "#c6dbef"]
    plt.figure(figsize=(10, 7))
    ax = sns.barplot(data=plot_data, x='Cohort', y='Count', hue='Category', palette=blue_shades)

    for p in ax.patches:
        ax.annotate(f'{int(p.get_height())}',
                    (p.get_x() + p.get_width() / 2., p.get_height()),
                    ha='center', va='center',
                    xytext=(0, 9),
                    textcoords='offset points',
                    fontsize=10)

    plt.title('CI Test and Coverage Adoption: Monoglot vs. Polyglot Projects')
    plt.xlabel('Project Cohort')
    plt.ylabel('Number of Projects')
    plt.ylim(0.1, max(total_mono, total_poly) * 1.15)
    plt.legend(title='Test Configuration')
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
    plt.savefig(output_file, dpi=300)
    plt.close()

    print(f"✅ CI adoption graph saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Generate CI adoption graph.")
    parser.add_argument("--mono-csv", required=True)
    parser.add_argument("--poly-csv", required=True)
    parser.add_argument("--mono-total-csv", required=True)
    parser.add_argument("--poly-total-csv", required=True)
    parser.add_argument("--output-file", required=True)
    args = parser.parse_args()

    create_ci_adoption_graph(
        args.mono_csv,
        args.poly_csv,
        args.mono_total_csv,
        args.poly_total_csv,
        args.output_file
    )

if __name__ == "__main__":
    main()
