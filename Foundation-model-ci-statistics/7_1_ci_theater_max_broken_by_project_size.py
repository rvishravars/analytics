import pandas as pd
import matplotlib.pyplot as plt

# Load broken builds and project size
broken_builds_df = pd.read_csv("data/7_ci_theater_broken_builds.csv")
project_sizes_df = pd.read_csv("data/2_ci_theater_project_sizes.csv")

# Merge on project name
df = pd.merge(broken_builds_df, project_sizes_df[["name", "Category"]], on="name", how="inner")

# Rename for clarity
df = df.rename(columns={
    "name": "Project",
    "Max Broken Days": "Max_Broken_Days",
    "Runs Analyzed": "Runs_Analyzed",
    "Category": "Size"
})

# Keep only projects with CI activity
df = df[df["Runs_Analyzed"] > 0]
df["Max_Broken_Days"] = pd.to_numeric(df["Max_Broken_Days"], errors="coerce")

# Compute percentiles
valid_data = df[df["Max_Broken_Days"].notna()]
median = valid_data["Max_Broken_Days"].median()
q3 = valid_data["Max_Broken_Days"].quantile(0.75)

# Plot boxplot of max broken durations grouped by project size
plt.figure(figsize=(8, 5))
df.boxplot(column="Max_Broken_Days", by="Size")

# Add median and 75th percentile lines
plt.axhline(y=median, color='green', linestyle='--', label=f"Median ({median:.1f} days)")
plt.axhline(y=q3, color='orange', linestyle='--', label=f"75th Percentile ({q3:.1f} days)")

# Labels and layout
plt.title("Max Broken Build Duration by Project Size")
plt.suptitle("")
plt.ylabel("Days")
plt.legend()
plt.tight_layout()
plt.savefig("data/7_1_ci_theater_max_broken_build_by_size.png", dpi=300, bbox_inches='tight')
