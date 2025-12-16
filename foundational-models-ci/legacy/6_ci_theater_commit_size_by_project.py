import pandas as pd
import matplotlib.pyplot as plt

# Load commit sizes and project sizes
commit_sizes_df = pd.read_csv("data/5_ci_theater_commit_sizes.csv")
project_sizes_df = pd.read_csv("data/2_ci_theater_project_sizes.csv")

# Merge data on project name
df = pd.merge(commit_sizes_df, project_sizes_df[["name", "Category"]], on="name", how="inner")

# Rename for clarity
df = df.rename(columns={
    "name": "Project",
    "Max Commit Size": "Max_Commit_Size",
    "Category": "Size"
})

# Convert to numeric
df["Max_Commit_Size"] = pd.to_numeric(df["Max_Commit_Size"], errors="coerce")

# Drop rows with NaNs
df = df.dropna(subset=["Max_Commit_Size"])

# ----- Plot 2: Max Commit Size -----
median_max = df["Max_Commit_Size"].median()
q3_max = df["Max_Commit_Size"].quantile(0.75)

plt.figure(figsize=(8, 5))
df.boxplot(column="Max_Commit_Size", by="Size")
plt.axhline(y=median_max, color='green', linestyle='--', label=f"Median ({median_max:.1f})")
plt.axhline(y=q3_max, color='orange', linestyle='--', label=f"75th Percentile ({q3_max:.1f})")
plt.title("Max Commit Size by Project Size")
plt.suptitle("")
plt.ylabel("Lines of Code")
plt.yscale('log')
plt.legend()
plt.tight_layout()
plt.savefig("data/6_max_commit_size_by_size.png", dpi=300, bbox_inches='tight')
