#!/usr/bin/env python3
"""
Generate CI Theater summary plots for Rust projects from:
  data/24_ci_theater_coverage_rust.csv

Outputs (created under ./figures):
  - ci_adoption_breakdown.png
  - ci_funnel_counts.png
  - coverage_boxplot.png
  - coverage_violin.png
  - ci_summary_table.csv
  - ci_plots_bundle.pdf
"""

import os
import math
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# ----------------------------- Config -----------------------------
INPUT_CSV = "data/24_ci_theater_coverage_rust.csv"
OUT_DIR = "figures"
os.makedirs(OUT_DIR, exist_ok=True)

# Columns expected in the CSV (case/whitespace tolerant)
COL_HAS_TESTS = "Has Tests (static)"
COL_TESTS_CI = "Tests in CI (configured)"
COL_TESTS_RECENT = "Tests in CI (recent runs)"  # optional for extra diagnostics
COL_COV_CI = "Coverage in CI (configured)"
COL_COV_LATEST = "Coverage Latest (%)"

# --------------------------- Utilities ----------------------------
def norm_yes_no(series: pd.Series) -> pd.Series:
    """Normalize Yes/No to booleans; anything else -> False (conservative)."""
    if series is None:
        return pd.Series(dtype=bool)
    return series.astype(str).str.strip().str.lower().map({"yes": True, "no": False}).fillna(False)

def numeric(series: pd.Series) -> pd.Series:
    """Coerce to numeric (NaN on failure)."""
    return pd.to_numeric(series, errors="coerce")

def save_fig(fig, path_png: str, pdf: PdfPages):
    fig.tight_layout()
    fig.savefig(path_png, dpi=300, bbox_inches="tight")
    pdf.savefig(fig)
    plt.close(fig)

# ----------------------------- Load -------------------------------
df = pd.read_csv(INPUT_CSV)

# Defensive: ensure required columns exist
for col in [COL_HAS_TESTS, COL_TESTS_CI, COL_COV_CI]:
    if col not in df.columns:
        raise ValueError(f"Missing expected column: {col}")

has_tests = norm_yes_no(df[COL_HAS_TESTS])
tests_in_ci = norm_yes_no(df[COL_TESTS_CI])
coverage_in_ci = norm_yes_no(df[COL_COV_CI])

# Optional diagnostics
tests_recent = norm_yes_no(df[COL_TESTS_RECENT]) if COL_TESTS_RECENT in df.columns else pd.Series([False]*len(df))

cov_latest = numeric(df[COL_COV_LATEST]) if COL_COV_LATEST in df.columns else pd.Series(dtype=float)

n = len(df)

# ------------------------- Derived Groups -------------------------
no_tests = ~has_tests
tests_but_no_ci = has_tests & ~tests_in_ci
ci_no_coverage = has_tests & tests_in_ci & ~coverage_in_ci
ci_with_coverage = has_tests & tests_in_ci & coverage_in_ci

# Sanity check: groups should partition projects (some may be “no tests”)
assert (no_tests | tests_but_no_ci | ci_no_coverage | ci_with_coverage).all()

counts = {
    "No tests": int(no_tests.sum()),
    "Tests but not in CI": int(tests_but_no_ci.sum()),
    "In CI without coverage": int(ci_no_coverage.sum()),
    "In CI with coverage": int(ci_with_coverage.sum()),
}
total = sum(counts.values())

summary_rows = []
for label, c in counts.items():
    pct = (c / total * 100.0) if total else 0.0
    summary_rows.append({"Category": label, "Count": c, "Percent": round(pct, 2)})

summary_df = pd.DataFrame(summary_rows)
summary_csv_path = os.path.join(OUT_DIR, "ci_summary_table.csv")
summary_df.to_csv(summary_csv_path, index=False)

# Funnel counts (stage-by-stage)
funnel_labels = ["Has tests", "Tests in CI", "Coverage in CI"]
funnel_counts = [
    int(has_tests.sum()),
    int((has_tests & tests_in_ci).sum()),
    int((has_tests & tests_in_ci & coverage_in_ci).sum()),
]

# Coverage subset (where we have numeric coverage)
coverage_mask = ci_with_coverage & cov_latest.notna()
coverage_values = cov_latest[coverage_mask]

# ----------------------------- Plots ------------------------------
bundle_pdf_path = os.path.join(OUT_DIR, "ci_plots_bundle.pdf")
with PdfPages(bundle_pdf_path) as pdf:

    # 1) Adoption breakdown (stacked bar as a single column)
    fig1, ax1 = plt.subplots(figsize=(6, 6))
    bottom = 0
    labels = list(counts.keys())
    values = [counts[k] for k in labels]

    # Plot segments (respecting toolkit rule: single plot, no custom colors)
    for i, (label, val) in enumerate(zip(labels, values)):
        ax1.bar([0], [val], bottom=[bottom])
        # Annotate percentage
        pct = (val / total * 100.0) if total else 0.0
        ax1.text(0, bottom + val / 2, f"{label}\n{val} ({pct:.1f}%)",
                 ha="center", va="center", fontsize=9)
        bottom += val

    ax1.set_title("CI Adoption Breakdown (Rust Projects)")
    ax1.set_xticks([0])
    ax1.set_xticklabels(["Projects"])
    ax1.set_ylabel("Number of repositories")
    ax1.set_ylim(0, max(total, 1))
    save_fig(fig1, os.path.join(OUT_DIR, "ci_adoption_breakdown.png"), pdf)

    # 2) Funnel bar chart: Has tests → Tests in CI → Coverage in CI
    fig2, ax2 = plt.subplots(figsize=(7, 4))
    ax2.bar(funnel_labels, funnel_counts)
    for x, y in zip(funnel_labels, funnel_counts):
        ax2.text(x, y, str(y), ha="center", va="bottom")
    ax2.set_title("CI Funnel (Stage Counts)")
    ax2.set_ylabel("Number of repositories")
    save_fig(fig2, os.path.join(OUT_DIR, "ci_funnel_counts.png"), pdf)

    # 3) Coverage distribution (boxplot), if we have any data
    if len(coverage_values) > 0:
        fig3, ax3 = plt.subplots(figsize=(6, 4))
        ax3.boxplot([coverage_values.dropna().values], labels=["Coverage Latest (%)"])
        ax3.set_title("Coverage (Latest) Distribution — Projects with Coverage in CI")
        ax3.set_ylabel("Percent")
        ax3.set_ylim(0, 100)
        save_fig(fig3, os.path.join(OUT_DIR, "coverage_boxplot.png"), pdf)

        # 4) Coverage distribution (violin)
        fig4, ax4 = plt.subplots(figsize=(6, 4))
        ax4.violinplot([coverage_values.dropna().values], showmeans=True, showmedians=True)
        ax4.set_xticks([1])
        ax4.set_xticklabels(["Coverage Latest (%)"])
        ax4.set_title("Coverage (Latest) Violin — Projects with Coverage in CI")
        ax4.set_ylabel("Percent")
        ax4.set_ylim(0, 100)
        save_fig(fig4, os.path.join(OUT_DIR, "coverage_violin.png"), pdf)
    else:
        # If no coverage numbers, include a small note plot for the PDF
        fig_note, ax_note = plt.subplots(figsize=(6, 2))
        ax_note.axis("off")
        ax_note.text(0.5, 0.5,
                     "No numeric coverage data found.\n(‘Coverage Latest (%)’ empty)",
                     ha="center", va="center")
        save_fig(fig_note, os.path.join(OUT_DIR, "coverage_no_data.png"), pdf)

print(f"[OK] Wrote summary table: {summary_csv_path}")
print(f"[OK] Wrote figures to: {OUT_DIR}/")
print(f"[OK] PDF bundle: {bundle_pdf_path}")
