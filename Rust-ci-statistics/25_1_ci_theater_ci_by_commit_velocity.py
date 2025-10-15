import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt
import git
import tempfile
import sys
from datetime import datetime, timezone, timedelta
import concurrent.futures
import seaborn as sns

# --- Helper Function for sizing ---
def categorize_project(sloc: int) -> str:
    """Categorizes a project based on its Source Lines of Code (SLOC)."""
    if sloc < 10000:
        return "Small"
    elif sloc < 100000:
        return "Medium"
    else:
        return "Large"

# --- Core Metric Calculation (Clones repos to get velocity) ---
def get_pre_ci_velocity(repo_name: str, clone_dir: str, ci_adoption_date_str: str) -> dict | None:
    """Clones a repo to calculate commit velocity before a GIVEN CI adoption date."""
    repo_url = f"https://github.com/{repo_name}.git"
    repo_path = os.path.join(clone_dir, repo_name.replace("/", "_"))
    try:
        print(f"  Cloning {repo_name} (this may take a moment)...", end="", flush=True)
        repo = git.Repo.clone_from(repo_url, repo_path)
        ci_adoption_date_str = ci_adoption_date_str.split('T')[0]
        ci_adoption_date = datetime.strptime(ci_adoption_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        window_start_date = ci_adoption_date - timedelta(days=182)
        commits = list(repo.iter_commits())
        pre_ci_commit_count = sum(1 for c in commits if window_start_date <= datetime.fromtimestamp(c.committed_date, tz=timezone.utc) < ci_adoption_date)
        velocity = pre_ci_commit_count / 26.0
        print(f" Done. Velocity={velocity:.2f}", flush=True)
        return {"Project": repo_name, "velocity": velocity}
    except Exception as e:
        print(f" Error during analysis for {repo_name}: {e}", flush=True)
        return None

# --- New function to handle the heavy computation and save results ---
def compute_and_cache_data(stats_file: str, sizes_file: str, cohort_name: str) -> pd.DataFrame:
    """Computes all metrics for a cohort and returns a DataFrame."""
    print(f"\n--- Processing cohort: {cohort_name} ---")
    stats_df = pd.read_csv(stats_file)
    sizes_df = pd.read_csv(sizes_file)

    stats_df.dropna(subset=['First CI Run Date'], inplace=True)
    stats_df['Time to First CI (months)'] = pd.to_numeric(stats_df['Time to First CI (months)'], errors='coerce')
    stats_df.dropna(subset=['Time to First CI (months)'], inplace=True)

    if stats_df.empty:
        print(f"Warning: No projects with CI adoption found in {stats_file}.")
        return pd.DataFrame()

    velocity_results = []
    MAX_WORKERS = (os.cpu_count() or 1) * 2
    
    # Ensure /temp directory exists
    os.makedirs('/temp', exist_ok=True)
    with tempfile.TemporaryDirectory(dir='/temp') as temp_dir:
        print(f"\nAnalyzing {len(stats_df)} repositories in {temp_dir}...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_repo = {
                executor.submit(get_pre_ci_velocity, row['Project'], temp_dir, row['First CI Run Date']): row['Project']
                for index, row in stats_df.iterrows()
            }
            for future in concurrent.futures.as_completed(future_to_repo):
                try:
                    metrics = future.result()
                    if metrics:
                        velocity_results.append(metrics)
                except Exception as exc:
                    print(f"\nAn exception occurred: {exc}", file=sys.stderr)
    
    if not velocity_results: return pd.DataFrame()
        
    velocity_df = pd.DataFrame(velocity_results)
    combined_df = pd.merge(stats_df, velocity_df, on='Project', how='inner')
    sizes_df["Size"] = sizes_df["rust_sloc"].apply(categorize_project)
    final_df = pd.merge(combined_df, sizes_df[["repo", "Size"]], left_on='Project', right_on='repo', how='inner')
    final_df['cohort'] = cohort_name
    
    return final_df

# --- New function to generate the plot from the cache file ---
def generate_plot_from_cache(cache_file: str, output_file: str, log_y: bool):
    """Reads the final data from a CSV and generates the scatter plot."""
    print(f"\n--- Generating plot from {cache_file} ---")
    try:
        final_df = pd.read_csv(cache_file)
    except FileNotFoundError:
        print(f"Error: Cache file not found at {cache_file}.", file=sys.stderr)
        print("Please run the script with '--recompute Y' first to generate it.", file=sys.stderr)
        return

    if final_df.empty:
        print("Error: Cache file is empty. No data to plot.", file=sys.stderr)
        return

    fig, axes = plt.subplots(1, 2, figsize=(18, 8), sharex=True, sharey=True)
    fig.suptitle("Relationship Between CI Adoption Time and Development Velocity", fontsize=20)
    
    cohorts = final_df['cohort'].unique()
    
    for i, cohort in enumerate(cohorts):
        ax = axes[i]
        cohort_df = final_df[final_df['cohort'] == cohort]
        
        sns.scatterplot(
            data=cohort_df,
            x="Time to First CI (months)",
            y="velocity",
            hue="Size",
            hue_order=["Small", "Medium", "Large"],
            alpha=0.7,
            ax=ax
        )
        ax.set_title(f"{cohort} Cohort")
        ax.set_xlabel("Time to First CI (months)")
        ax.set_ylabel("Pre-CI Commit Velocity (commits/week)")
        ax.grid(True)

        # Set y-axis to log scale if requested
        if log_y:
            ax.set_yscale('log')
            ax.set_ylabel("Pre-CI Commit Velocity (commits/week, log scale)")
        
        print(f"\nSummary for {cohort} cohort:")
        print(cohort_df[['velocity', 'Time to First CI (months)']].describe())
        
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"\n✅ Combined plot saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Analyze and plot CI adoption dynamics.")
    parser.add_argument("--mono-stats-file", required=True, help="Path to monoglot stats CSV.")
    parser.add_argument("--mono-sizes-file", required=True, help="Path to monoglot sizes CSV.")
    parser.add_argument("--poly-stats-file", required=True, help="Path to polyglot stats CSV.")
    parser.add_argument("--poly-sizes-file", required=True, help="Path to polyglot sizes CSV.")
    parser.add_argument("--cache-file", required=True, help="Path to store/read the intermediate CSV results.")
    parser.add_argument("--output-file", required=True, help="Path to save the final plot PNG.")
    parser.add_argument("--recompute", choices=['Y', 'N'], required=True, help="'Y' to recompute all data, 'N' to plot from cache.")
    # Add new argument for log scale
    parser.add_argument("--log-y", action='store_true', help="Set the y-axis of the plot to a logarithmic scale.")
    args = parser.parse_args()

    if args.recompute == 'Y':
        # Compute data for both cohorts
        mono_df = compute_and_cache_data(args.mono_stats_file, args.mono_sizes_file, "Monoglot")
        poly_df = compute_and_cache_data(args.poly_stats_file, args.poly_sizes_file, "Polyglot")
        
        # Combine and save to the cache file
        combined_df = pd.concat([mono_df, poly_df], ignore_index=True)
        combined_df.to_csv(args.cache_file, index=False)
        print(f"\n✅ Computation complete. Final data saved to {args.cache_file}")

    # Generate the plot from the (newly created or existing) cache file
    generate_plot_from_cache(args.cache_file, args.output_file, args.log_y)

if __name__ == "__main__":
    main()