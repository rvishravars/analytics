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
    elif sloc < 1000000:
        return "Large"

# --- Coverage Analysis functions ---
# Expected CSV columns for coverage analysis
COL_HAS_TESTS = "Has Tests (static)"
COL_TESTS_CI = "Tests in CI (configured)"
COL_COV_CI = "Coverage in CI (configured)"
COL_COV_LATEST = "Coverage Latest (%)"

def norm_yes_no(series: pd.Series) -> pd.Series:
    """Normalize Yes/No values to booleans; anything else -> False."""
    return series.astype(str).str.strip().str.lower().map({"yes": True, "no": False}).fillna(False)

def numeric(series: pd.Series) -> pd.Series:
    """Coerce series to numeric (NaN on failure)."""
    return pd.to_numeric(series, errors="coerce")

def load_coverage_data(input_csv: str, cohort_name: str) -> pd.Series:
    """
    Load the CSV file and extract numeric coverage values for projects
    with coverage configured in CI.
    """
    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        print(f"Error: Input file not found at '{input_csv}'")
        return pd.Series(dtype=float)
    
    required_cols = [COL_HAS_TESTS, COL_TESTS_CI, COL_COV_CI]
    for col in required_cols:
        if col not in df.columns:
            print(f"Error: Missing expected column '{col}' in {input_csv}")
            return pd.Series(dtype=float)
    
    has_tests = norm_yes_no(df[COL_HAS_TESTS])
    tests_in_ci = norm_yes_no(df[COL_TESTS_CI])
    cov_in_ci = norm_yes_no(df[COL_COV_CI])
    
    # Determine projects that have CI with coverage configured.
    ci_with_coverage = has_tests & tests_in_ci & cov_in_ci
    
    if COL_COV_LATEST in df.columns:
        cov_latest = numeric(df[COL_COV_LATEST])
    else:
        cov_latest = pd.Series(dtype=float)
    
    # Select numeric coverage values where coverage is configured and valid
    mask = ci_with_coverage & cov_latest.notna()
    coverage_values = cov_latest[mask]
    
    if coverage_values.empty:
        print(f"Warning: No numeric coverage data found for {cohort_name}.")
    else:
        print(f"{cohort_name}: {len(coverage_values)} projects with numeric coverage data found.")
    return coverage_values

def perform_coverage_analysis(args):
    # Load coverage data for each cohort
    mono_cov = load_coverage_data(args.mono_input_csv, args.mono_cohort_name)
    poly_cov = load_coverage_data(args.poly_input_csv, args.poly_cohort_name)
    
    # Only include non-empty series
    data = {}
    labels = []
    if not mono_cov.empty:
        data[args.mono_cohort_name] = mono_cov
        labels.append(args.mono_cohort_name)
    if not poly_cov.empty:
        data[args.poly_cohort_name] = poly_cov
        labels.append(args.poly_cohort_name)
        
    if not data:
        print("Error: No valid coverage data found for either cohort. Exiting.")
        return

    # --- Summary Statistics ---
    summary_stats = []
    for name, cov_series in data.items():
        stats = {
            "Cohort": name,
            "Mean": cov_series.mean(),
            "1st Quartile": cov_series.quantile(0.25),
            "3rd Quartile": cov_series.quantile(0.75),
            "Count": len(cov_series)
        }
        summary_stats.append(stats)
    if summary_stats:
        summary_df = pd.DataFrame(summary_stats).set_index("Cohort")
        print("\n--- Coverage Summary Statistics ---")
        print(summary_df.round(2).to_string())
        print("-------------------------------------\n")
    
    # Prepare data for plotting: list with coverage arrays in the desired order.
    plot_data = [data[label].dropna().values for label in labels]
    
    # Create a composite figure with two subplots: boxplot and violin plot.
    fig, (ax_box, ax_violin) = plt.subplots(2, 1, figsize=(8, 10))
    #fig.suptitle("Coverage Distribution Comparison", fontsize=16)
    
    # Boxplot
    bp = ax_box.boxplot(plot_data, labels=labels, patch_artist=True)
    ax_box.set_ylabel("Coverage Latest (%)")
    #ax_box.set_title("Boxplot")
    ax_box.set_ylim(0, 100)
    for patch in bp["boxes"]:
        patch.set_facecolor("white")
    
    # Violin plot
    vp = ax_violin.violinplot(plot_data, showmeans=True, showmedians=True)
    ax_violin.set_xticks(range(1, len(labels) + 1))
    ax_violin.set_xticklabels(labels)
    ax_violin.set_ylabel("Coverage Latest (%)")
    #ax_violin.set_title("Violin Plot")
    ax_violin.set_ylim(0, 100)
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
    plt.savefig(args.output_file, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✅ Combined coverage plot saved to {args.output_file}")

# --- NEW: Coverage by Size Analysis ---
def generate_coverage_by_size_plot(coverage_file: str, sizes_file: str, cohort_name: str, ax):
    """
    Generates a boxplot of test coverage by project size for a single cohort.
    """
    try:
        coverage_df = pd.read_csv(coverage_file)
        sizes_df = pd.read_csv(sizes_file)
    except FileNotFoundError as e:
        print(f"Error: Input file not found: {e.filename}")
        return False

    # Merge coverage and size data
    df = pd.merge(coverage_df, sizes_df, on="name", how="inner")

    if df.empty:
        print(f"Warning: No matching projects found between {coverage_file} and {sizes_file} for cohort '{cohort_name}'.")
        return False

    # Filter for projects with valid coverage data
    has_tests = norm_yes_no(df[COL_HAS_TESTS])
    tests_in_ci = norm_yes_no(df[COL_TESTS_CI])
    cov_in_ci = norm_yes_no(df[COL_COV_CI])
    ci_with_coverage = has_tests & tests_in_ci & cov_in_ci
    
    df[COL_COV_LATEST] = numeric(df[COL_COV_LATEST])
    
    mask = ci_with_coverage & df[COL_COV_LATEST].notna()
    df = df[mask].copy()

    if df.empty:
        print(f"Warning: No projects with valid coverage data found for cohort '{cohort_name}'.")
        return False

    # Categorize by size
    df["Size"] = df["rust_sloc"].apply(categorize_project)
    category_order = ["Small", "Medium", "Large"]
    df["Size"] = pd.Categorical(df["Size"], categories=category_order, ordered=True)
    df.sort_values("Size", inplace=True)

    # Create boxplot
    sns.boxplot(data=df, x="Size", y=COL_COV_LATEST, order=category_order, ax=ax, boxprops=dict(facecolor='white'))
    ax.set_title(f"{cohort_name} Projects")
    ax.set_xlabel("Project Size")
    ax.set_ylabel("Latest Coverage (%)")
    ax.set_ylim(0, 105)
    ax.grid(True, axis='y')
    for tick in ax.get_xticklabels():
        tick.set_rotation(10)

    # Print summary statistics
    summary = df.groupby("Size")[COL_COV_LATEST].agg(['mean', 'median', 'count', 'std']).round(2)
    print(f"\nSummary for {cohort_name} cohort (Coverage by Size):")
    print(summary)

    return True

def perform_coverage_by_size_analysis(args):
    """
    Creates a side-by-side comparison of test coverage by project size for
    monoglot and polyglot cohorts.
    """
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=True)
    #fig.suptitle("Test Coverage by Project Size", fontsize=16)

    print("Processing Monoglot cohort...")
    mono_success = generate_coverage_by_size_plot(
        coverage_file=args.mono_input_csv,
        sizes_file=args.mono_sizes_file,
        cohort_name=args.mono_cohort_name,
        ax=axes[0]
    )

    print("\nProcessing Polyglot cohort...")
    poly_success = generate_coverage_by_size_plot(
        coverage_file=args.poly_input_csv,
        sizes_file=args.poly_sizes_file,
        cohort_name=args.poly_cohort_name,
        ax=axes[1]
    )

    if not mono_success and not poly_success:
        print("\nError: Failed to generate plots for both cohorts.")
        return

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
    plt.savefig(args.output_file, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"\n✅ Combined coverage-by-size plot saved to {args.output_file}")

# --- CI Adoption Analysis function ---
def perform_ci_adoption_analysis(args):
    """
    Analyze CI adoption using a CSV with a 'has_ci' column.
    If --ci-input-csv is provided, it is used.
    Otherwise, the script reads and concatenates --mono-input-csv and --poly-input-csv.
    If the required 'has_ci' column is missing, the script uses "Tests in CI (configured)" as a fallback.
    Produces a bar plot counting projects with and without CI.
    """
    if args.ci_input_csv:
        try:
            df = pd.read_csv(args.ci_input_csv)
        except FileNotFoundError as e:
            print(f"Error: File not found: {e.filename}")
            return
    else:
        try:
            df_mono = pd.read_csv(args.mono_input_csv)
            df_poly = pd.read_csv(args.poly_input_csv)
        except FileNotFoundError as e:
            print(f"Error: File not found: {e.filename}")
            return
        df = pd.concat([df_mono, df_poly], ignore_index=True)
    
    # If 'has_ci' is not present, try to derive it from "Tests in CI (configured)"
    if 'has_ci' not in df.columns:
        if "Tests in CI (configured)" in df.columns:
            print("Note: 'has_ci' column not found. Deriving CI adoption from 'Tests in CI (configured)'.")
            df['has_ci'] = df["Tests in CI (configured)"]
        else:
            print("Error: Expected column 'has_ci' or 'Tests in CI (configured)' not found in the CSV file(s).")
            return

    # Convert yes/no to booleans
    df['Has CI'] = df['has_ci'].astype(str).str.strip().str.lower().map({'yes': True, 'no': False})
    
    # Count projects with and without CI
    counts = df['Has CI'].value_counts().sort_index()
    # Map boolean index to labels
    counts.index = counts.index.map({True: "CI Adopted", False: "No CI"})
    
    # Create a bar plot
    plt.figure(figsize=(6,4))
    counts.plot(kind='bar', color=['green', 'red'])
    plt.title("CI Adoption Among Rust Projects")
    plt.xlabel("CI Status")
    plt.ylabel("Number of Projects")
    plt.xticks(rotation=0)
    plt.tight_layout()
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
    plt.savefig(args.output_file, dpi=300)
    plt.close()
    print(f"✅ CI adoption plot saved to {args.output_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Generate analysis images for Rust projects (coverage analysis or CI adoption analysis)."
    )
    parser.add_argument("--mode", required=True, choices=["coverage", "ci-adoption", "coverage-by-size"],
                        help="Mode to run: 'coverage' for overall coverage comparison, "
                             "'ci-adoption' for CI adoption analysis, "
                             "'coverage-by-size' for coverage broken down by project size.")

    # Coverage analysis arguments
    parser.add_argument("--mono-input-csv", help="CSV file for monoglot coverage data.")
    parser.add_argument("--poly-input-csv", help="CSV file for polyglot coverage data.")
    parser.add_argument("--mono-cohort-name", help="Name for the monoglot cohort (e.g., 'Monoglot').")
    parser.add_argument("--poly-cohort-name", help="Name for the polyglot cohort (e.g., 'Polyglot').")
    
    # New arguments for coverage-by-size
    parser.add_argument("--mono-sizes-file", help="Path to the monoglot project sizes (SLOC) CSV file.")
    parser.add_argument("--poly-sizes-file", help="Path to the polyglot project sizes (SLOC) CSV file.")
    
    # CI adoption analysis argument (optional)
    parser.add_argument("--ci-input-csv", help="CSV file for CI adoption analysis (expects 'has_ci' column).")
    
    # Common output file argument
    parser.add_argument("--output-file", required=True, help="Path to save the output plot (PNG).")
    
    args = parser.parse_args()

    if args.mode == "coverage":
        # Check required arguments for coverage mode
        if not all([args.mono_input_csv, args.poly_input_csv, args.mono_cohort_name, args.poly_cohort_name]):
            parser.error("For coverage mode, please provide --mono-input-csv, --poly-input-csv, --mono-cohort-name, and --poly-cohort-name.")
        perform_coverage_analysis(args)
    elif args.mode == "ci-adoption":
        # For CI adoption mode, if --ci-input-csv is not provided, require mono and poly input CSVs.
        if not args.ci_input_csv and not (args.mono_input_csv and args.poly_input_csv):
            parser.error("For ci-adoption mode, please provide either --ci-input-csv or both --mono-input-csv and --poly-input-csv.")
        perform_ci_adoption_analysis(args)
    elif args.mode == "coverage-by-size":
        # Check required arguments for the new mode
        required_for_size = [
            args.mono_input_csv, args.poly_input_csv,
            args.mono_sizes_file, args.poly_sizes_file,
            args.mono_cohort_name, args.poly_cohort_name
        ]
        if not all(required_for_size):
            parser.error("For coverage-by-size mode, you must provide all --mono/poly-input-csv, --mono/poly-sizes-file, and --mono/poly-cohort-name arguments.")
        perform_coverage_by_size_analysis(args)

if __name__ == "__main__":
    main()