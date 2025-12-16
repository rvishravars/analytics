import pandas as pd
import matplotlib.pyplot as plt

# Load CSV files
long_builds_df = pd.read_csv("data/8_ci_theater_long_builds.csv")
project_sizes_df = pd.read_csv("data/2_ci_theater_project_sizes.csv")

# Merge on project name
df = pd.merge(long_builds_df, project_sizes_df[["name", "Category"]], on="name", how="inner")

# Clean and convert relevant fields
df["Avg Duration (min)"] = pd.to_numeric(df["Avg Duration (min)"], errors="coerce")
df["Runs Counted"] = pd.to_numeric(df["Runs Counted"], errors="coerce")

# Filter out projects with no build data
df = df[df["Runs Counted"] > 0]

# Compute percentiles
valid_data = df[df["Avg Duration (min)"].notna()]
median = valid_data["Avg Duration (min)"].median()
q3 = valid_data["Avg Duration (min)"].quantile(0.75)

# Plot boxplot grouped by project size
plt.figure(figsize=(8, 5))
df.boxplot(column="Avg Duration (min)", by="Category")

# Annotate reference and percentile lines
plt.axhline(y=10, color='red', linestyle='--', label="10-minute Threshold")
plt.axhline(y=median, color='green', linestyle='--', label=f"Median ({median:.2f} min)")
plt.axhline(y=q3, color='orange', linestyle='--', label=f"75th Percentile ({q3:.2f} min)")

# Labels and layout
plt.title("Average Build Duration by Project Size")
plt.suptitle("")  # Remove automatic group title
plt.xlabel("Project Size")
plt.ylabel("Avg Build Duration (minutes)")
plt.legend()
plt.tight_layout()
plt.savefig("data/8_1_avg_build_duration_by_size.png", dpi=300, bbox_inches='tight')
