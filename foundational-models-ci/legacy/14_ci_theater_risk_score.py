import pandas as pd
import matplotlib.pyplot as plt

# Load CSVs
commit_freq_df = pd.read_csv("data/3_ci_theater_commit_frequency.csv")
broken_builds_df = pd.read_csv("data/7_ci_theater_broken_builds.csv")
project_sizes_df = pd.read_csv("data/2_ci_theater_project_sizes.csv")

# Merge data on project name
df = pd.merge(commit_freq_df, broken_builds_df, on="name", how="inner")
df = pd.merge(df, project_sizes_df[["name", "Category"]], on="name", how="left")

# Rename columns for clarity
df = df[[
    "name",
    "Avg Commits/Weekday (Mon–Fri)",
    "Runs Analyzed",
    "Broken >4 Days",
    "Max Broken Days",
    "Category"
]].copy()

df.columns = [
    "Project",
    "Avg_Weekday_Commits",
    "CI_Runs_Analyzed",
    "Builds_Broken_Over_4_Days",
    "Max_Broken_Duration",
    "Size_Category"
]

# Convert numerics
df["Avg_Weekday_Commits"] = pd.to_numeric(df["Avg_Weekday_Commits"], errors="coerce")
df["Builds_Broken_Over_4_Days"] = pd.to_numeric(df["Builds_Broken_Over_4_Days"], errors="coerce")
df["Max_Broken_Duration"] = pd.to_numeric(df["Max_Broken_Duration"], errors="coerce")

# Filter only projects with CI runs
df = df[df["CI_Runs_Analyzed"] > 0]

# Compute CI Theater Risk Score
df["Risk_Infrequent_Commits"] = (df["Avg_Weekday_Commits"] < 2.36).astype(int)
df["Risk_Broken_4plus_Days"] = (df["Builds_Broken_Over_4_Days"] > 0).astype(int)
df["Risk_Max_Broken_Over50"] = (df["Max_Broken_Duration"] > 50).astype(int)
df["CI_Risk_Score"] = df[[
    "Risk_Infrequent_Commits",
    "Risk_Broken_4plus_Days",
    "Risk_Max_Broken_Over50"
]].sum(axis=1)

# Group by project size and compute average risk
grouped = df.groupby("Size_Category")["CI_Risk_Score"].mean().sort_values(ascending=False)

# Plot
plt.figure(figsize=(8, 5))
colors = plt.cm.RdYlGn_r(grouped / 3)  # normalize over max score 3
plt.bar(grouped.index, grouped.values, color=colors)

plt.ylabel("Average CI Theater Risk Score")
plt.xlabel("Project Size Category")
plt.title("CI Theater Risk by Project Size")
plt.ylim(0, 3)
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()
plt.savefig("data/14_ci_theater_risk_by_size.png", dpi=300, bbox_inches="tight")
