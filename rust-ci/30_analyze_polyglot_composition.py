#!/usr/bin/env python3
"""
Analyze polyglot Rust repos (from polyglot_rust_repo_summary.csv).
Generates summary statistics, aggregate SLOC, Rust vs co-language pair analysis,
and splits results into Rust-majority vs Rust-minority projects.
"""

import argparse
import pandas as pd
import matplotlib.pyplot as plt
import os
import json


def get_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Analyze polyglot Rust repo composition.")
    parser.add_argument(
        "--input-csv",
        default="data/29_polyglot_rust_repos_summary.csv",
        help="Path to the polyglot summary CSV from 29_collect_language_sloc.py.",
    )
    parser.add_argument(
        "--output-dir", default="figures/polyglot_analysis", help="Directory to save the output plots and CSVs."
    )
    return parser.parse_args()


def main():
    args = get_args()
    os.makedirs(args.output_dir, exist_ok=True)

    # ----------------------- Load data --------------------
    try:
        df = pd.read_csv(args.input_csv)
    except FileNotFoundError:
        print(f"Error: Input file not found at '{args.input_csv}'")
        return

    # Ensure correct dtypes
    df["total_sloc"] = pd.to_numeric(df["total_sloc"], errors="coerce")
    df["rust_sloc"] = pd.to_numeric(df["rust_sloc"], errors="coerce")
    df["rust_share_pct"] = pd.to_numeric(df["rust_share_pct"], errors="coerce")
    df["num_langs"] = pd.to_numeric(df["num_langs"], errors="coerce")

    # --------------------- Summary Stats ------------------
    summary = {
        "total_repos": len(df),
        "median_rust_share_pct": df["rust_share_pct"].median(),
        "mean_rust_share_pct": df["rust_share_pct"].mean(),
        "repos_rust_majority": (df["rust_share_pct"] > 50).sum(),
        "repos_rust_minority": (df["rust_share_pct"] <= 50).sum(),
        "max_languages": df["num_langs"].max(),
        "median_languages": df["num_langs"].median(),
    }

    print("=== Summary Statistics ===")
    for k, v in summary.items():
        print(f"{k}: {v}")

    # --------------------- Histograms ---------------------
    plt.figure(figsize=(8, 5))
    df["num_langs"].hist(bins=20)
    plt.title("Distribution of Number of Languages per Repo")
    plt.xlabel("Number of Languages")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(args.output_dir, "num_langs_hist.png"))

    plt.figure(figsize=(8, 5))
    df["rust_share_pct"].hist(bins=30)
    plt.title("Distribution of Rust Share (%)")
    plt.xlabel("Rust Share %")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(args.output_dir, "rust_share_hist.png"))

    # ------------------- Scatterplots ---------------------
    plt.figure(figsize=(8, 6))
    plt.scatter(df["total_sloc"], df["rust_share_pct"], alpha=0.5)
    plt.xscale("log")
    plt.title("Rust Share vs. Project Size")
    plt.xlabel("Total SLOC (log scale)")
    plt.ylabel("Rust Share (%)")
    plt.tight_layout()
    plt.savefig(os.path.join(args.output_dir, "rust_share_vs_size.png"))

    # ---------------- Explode Languages -------------------
    rows = []
    for _, r in df.iterrows():
        if pd.isna(r["languages_json"]):
            continue
        try:
            langs = json.loads(r["languages_json"])
            for lang, sloc in langs.items():
                if lang != "Rust":
                    rows.append({
                        "repo": r["repo"],
                        "rust_share_pct": r["rust_share_pct"],
                        "language": lang,
                        "sloc": sloc,
                        "is_majority": r["rust_share_pct"] > 50
                    })
        except Exception:
            pass

    langs_df = pd.DataFrame(rows)

    # ---------------- Co-language frequency ----------------
    top_co = langs_df["language"].value_counts().head(15)
    plt.figure(figsize=(10, 6))
    top_co.plot(kind="bar")
    plt.title("Most Common Co-languages with Rust (by repo count)")
    plt.xlabel("Language")
    plt.ylabel("Number of Repos")
    plt.tight_layout()
    plt.savefig(os.path.join(args.output_dir, "top_co_languages.png"))

    # ---------------- Aggregate SLOC per language ----------------
    agg_lang_sloc = langs_df.groupby("language")["sloc"].sum().sort_values(ascending=False)
    agg_csv = os.path.join(args.output_dir, "aggregate_language_sloc.csv")
    agg_lang_sloc.to_csv(agg_csv, header=["total_sloc"])
    print(f"\nAggregate SLOC per language saved to {agg_csv}")

    plt.figure(figsize=(10, 6))
    agg_lang_sloc.head(15).plot(kind="bar")
    plt.title("Top 15 Co-languages with Rust (by aggregate SLOC)")
    plt.xlabel("Language")
    plt.ylabel("Total SLOC (across all repos)")
    plt.tight_layout()
    plt.savefig(os.path.join(args.output_dir, "aggregate_sloc_top_languages.png"))

    # ---------------- Rust vs Co-language Pair Analysis ----------------
    pair_stats = (
        langs_df.groupby("language")["rust_share_pct"]
        .agg(["count", "mean", "median"])
        .sort_values("count", ascending=False)
    )
    pair_csv = os.path.join(args.output_dir, "rust_vs_colanguage_pairs.csv")
    pair_stats.to_csv(pair_csv)
    print(f"Rust vs. co-language pair stats saved to {pair_csv}")

    plt.figure(figsize=(10, 6))
    pair_stats.head(12).sort_values("mean", ascending=False)["mean"].plot(kind="barh")
    plt.title("Average Rust Share (%) in Rust+X Projects (Top 12 by repo count)")
    plt.xlabel("Average Rust Share (%)")
    plt.ylabel("Language")
    plt.tight_layout()
    plt.savefig(os.path.join(args.output_dir, "rust_share_by_colanguage.png"))

    # ---------------- Split: Majority vs Minority ----------------
    maj = langs_df[langs_df["is_majority"]]
    minn = langs_df[~langs_df["is_majority"]]

    maj_stats = (
        maj.groupby("language")["rust_share_pct"]
        .agg(["count", "mean", "median"])
        .sort_values("count", ascending=False)
    )
    min_stats = (
        minn.groupby("language")["rust_share_pct"]
        .agg(["count", "mean", "median"])
        .sort_values("count", ascending=False)
    )

    maj_csv = os.path.join(args.output_dir, "rust_majority_colanguage_stats.csv")
    min_csv = os.path.join(args.output_dir, "rust_minority_colanguage_stats.csv")
    maj_stats.to_csv(maj_csv)
    min_stats.to_csv(min_csv)

    print(f"Rust-majority co-language stats saved to {maj_csv}")
    print(f"Rust-minority co-language stats saved to {min_csv}")

    # Plots: compare top co-languages in majority vs minority
    plt.figure(figsize=(10, 6))
    maj_stats.head(10)["count"].plot(kind="bar", alpha=0.7, label="Rust-majority")
    min_stats.head(10)["count"].plot(kind="bar", alpha=0.7, label="Rust-minority", color="orange")
    plt.title("Top Co-languages in Majority vs Minority Rust Projects")
    plt.xlabel("Language")
    plt.ylabel("Number of Repos")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(args.output_dir, "colanguage_counts_majority_vs_minority.png"))

    print(f"\n✅ Figures and CSVs saved in {args.output_dir}/")


if __name__ == "__main__":
    main()
