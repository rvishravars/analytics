#!/usr/bin/env python3
import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def process_cohort(bugs_file: str, cohort_name: str):
    try:
        bugs_df = pd.read_csv(bugs_file)
    except FileNotFoundError as e:
        print(f"Error: Input file not found: {e.filename}")
        return None
    
    if bugs_df.empty:
        print(f"No data available for {cohort_name}.")
        return None

    # Compute bug ratio if sum of before+after > 0; else keep as NaN
    bugs_df["Total Bugs"] = bugs_df["Bug Issues Before CI"] + bugs_df["Bug Issues After CI"]
    bugs_df["Bug Ratio"] = bugs_df.apply(lambda row: row["Bug Issues After CI"] / row["Total Bugs"]
                               if row["Total Bugs"] > 0 else None, axis=1)
    return bugs_df

def main():
    parser = argparse.ArgumentParser(        description="Combined analysis: Bug issues by project size for monoglot and polyglot cohorts."

    )
    parser.add_argument("--mono-bugs-file", required=True, help="Path to the monoglot bug issues CSV file.")
    parser.add_argument("--poly-bugs-file", required=True, help="Path to the polyglot bug issues CSV file.")
    parser.add_argument("--output-file", required=True, help="Path to save the combined output PNG file.")
    parser.add_argument("--mono-cohort-name", default="Monoglot", help="Name of the monoglot cohort.")
    parser.add_argument("--poly-cohort-name", default="Polyglot", help="Name of the polyglot cohort.")
    args = parser.parse_args()

    mono_df = process_cohort(args.mono_bugs_file, args.mono_cohort_name)
    poly_df = process_cohort(args.poly_bugs_file, args.poly_cohort_name)

    if mono_df is None and poly_df is None:
        print("No valid data to plot for either cohort.")
        return

    # Concatenate the two dataframes
    if mono_df is not None and poly_df is not None:
        combined_df = pd.concat([mono_df[["Bug Ratio", "Bug Issues Before CI", "Bug Issues After CI"]].assign(cohort=args.mono_cohort_name),
                                 poly_df[["Bug Ratio", "Bug Issues Before CI", "Bug Issues After CI"]].assign(cohort=args.poly_cohort_name)])
    elif mono_df is not None:
        combined_df = mono_df[["Bug Ratio", "Bug Issues Before CI", "Bug Issues After CI"]].assign(cohort=args.mono_cohort_name)
    elif poly_df is not None:
         combined_df = poly_df[["Bug Ratio", "Bug Issues Before CI", "Bug Issues After CI"]].assign(cohort=args.poly_cohort_name)
    else:
        print("No data available to combine.")
        return

    # Melt the dataframe for easier plotting with seaborn
    plot_df = pd.melt(combined_df,
                      id_vars=["cohort"],
                      value_vars=["Bug Issues Before CI", "Bug Issues After CI"],
                      var_name="Bug Type",
                      value_name="Bug Count")

    # Calculate and print summary statistics
    summary = plot_df.groupby(["cohort", "Bug Type"])["Bug Count"].agg(
        mean='mean',
        first_quartile=lambda x: x.quantile(0.25),
        third_quartile=lambda x: x.quantile(0.75)
    ).round(2)
    print("\n--- Summary Statistics for Bug Issues ---")
    print(summary.to_string())
    print("-" * 40 + "\n")


    # Create a single boxplot showing bug counts before and after CI for both cohorts
    plt.figure(figsize=(10, 7))
    
    order = [name for name, df in [(args.mono_cohort_name, mono_df), (args.poly_cohort_name, poly_df)] if df is not None]

    palette = {"Bug Issues Before CI": "skyblue", "Bug Issues After CI": "lightsalmon"}

    sns.boxplot(x="cohort", y="Bug Count",
                hue="Bug Type", data=plot_df,
                order=order,
                palette=palette,
                dodge=True,
                showfliers=False)  # Ensure boxes are dodged for better readability

    plt.title("Bug Issues Before and After CI Adoption by Cohort")
    plt.xlabel("Cohort")
    plt.ylabel("Number of Bug Issues")
    #plt.yscale("log")
    plt.grid(True, axis='y')
    plt.tight_layout()

    os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
    plt.savefig(args.output_file, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✅ Combined bug analysis plot saved to {args.output_file}")
if __name__ == "__main__":
    main()