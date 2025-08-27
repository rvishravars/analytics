#!/usr/bin/env python3
"""
Analyze polyglot Rust repos (from polyglot_rust_repo_summary.csv).
Generates summary statistics and visualizations for scientific reporting,
including Rust vs. co-language pair analysis.
"""

import pandas as pd
import matplotlib.pyplot as plt
import os
import json

# ----------------------- Config -----------------------
IN_CSV = "data/polyglot_rust_repo_summary.csv"
OUT_DIR = "figures"
os.makedirs(OUT_DIR, exist_ok=True)

# ----------------------- Load data --------------------
df = pd.read_csv(IN_CSV)

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
plt.savefig(os.path.join(OUT_DIR, "num_langs_hist.png"))

plt.figure(figsize=(8, 5))
df["rust_share_pct"].hist(bins=30)
plt.title("Distribution of Rust Share (%)")
plt.xlabel("Rust Share %")
plt.ylabel("Count")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "rust_share_hist.png"))

# ------------------- Scatterplots ---------------------
plt.figure(figsize=(8, 6))
plt.scatter(df["total_sloc"], df["rust_share_pct"], alpha=0.5)
plt.xscale("log")  # log scale for sloc
plt.title("Rust Share vs. Project Size")
plt.xlabel("Total SLOC (log scale)")
plt.ylabel("Rust Share (%)")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "rust_share_vs_size.png"))

# ---------------- Top co-languages --------------------
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
                    "sloc": sloc
                })
    except Exception:
        pass

langs_df = pd.DataFrame(rows)

# Count frequency of languages across repos
top_co = langs_df["language"].value_counts().head(15)
plt.figure(figsize=(10, 6))
top_co.plot(kind="bar")
plt.title("Most Common Co-languages with Rust (by repo count)")
plt.xlabel("Language")
plt.ylabel("Number of Repos")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "top_co_languages.png"))

# ---------------- Aggregate SLOC per language ----------------
agg_lang_sloc = langs_df.groupby("language")["sloc"].sum().sort_values(ascending=False)

agg_csv = os.path.join(OUT_DIR, "aggregate_language_sloc.csv")
agg_lang_sloc.to_csv(agg_csv, header=["total_sloc"])
print(f"\nAggregate SLOC per language saved to {agg_csv}")

plt.figure(figsize=(10, 6))
agg_lang_sloc.head(15).plot(kind="bar")
plt.title("Top 15 Co-languages with Rust (by aggregate SLOC)")
plt.xlabel("Language")
plt.ylabel("Total SLOC (across all repos)")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "aggregate_sloc_top_languages.png"))

# ---------------- Rust vs Co-language Pair Analysis ----------------
pair_stats = (
    langs_df.groupby("language")["rust_share_pct"]
    .agg(["count", "mean", "median"])
    .sort_values("count", ascending=False)
)

pair_csv = os.path.join(OUT_DIR, "rust_vs_colanguage_pairs.csv")
pair_stats.to_csv(pair_csv)
print(f"Rust vs. co-language pair stats saved to {pair_csv}")

# Plot top-N co-languages by avg Rust share
topN = 12
plt.figure(figsize=(10, 6))
pair_stats.head(topN).sort_values("mean", ascending=False)["mean"].plot(kind="barh")
plt.title(f"Average Rust Share (%) in Rust+X Projects (Top {topN} by repo count)")
plt.xlabel("Average Rust Share (%)")
plt.ylabel("Language")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "rust_share_by_colanguage.png"))

print(f"\nFigures + CSVs saved in {OUT_DIR}/")
