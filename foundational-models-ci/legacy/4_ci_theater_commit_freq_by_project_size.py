import pandas as pd
import matplotlib.pyplot as plt

# Load commit frequency and project size
commit_freq_df = pd.read_csv("data/3_ci_theater_commit_frequency.csv")
project_sizes_df = pd.read_csv("data/2_ci_theater_project_sizes.csv")

# Merge on project name
df = pd.merge(commit_freq_df, project_sizes_df[["name", "Category"]], on="name", how="inner")

# Rename for clarity
df = df.rename(columns={
    "name": "Project",
    "Avg Commits/Weekday (Mon–Fri)": "Avg_Commits_Weekday",
    "Category": "Size"
})

# Convert to numeric
df["Avg_Commits_Weekday"] = pd.to_numeric(df["Avg_Commits_Weekday"], errors="coerce")

# Drop NaNs before computing percentiles
valid_data = df[df["Avg_Commits_Weekday"].notna()]
median = valid_data["Avg_Commits_Weekday"].median()
q3 = valid_data["Avg_Commits_Weekday"].quantile(0.75)

# Plot boxplot of Avg Commits/Weekday grouped by project size
plt.figure(figsize=(8, 5))
df.boxplot(column="Avg_Commits_Weekday", by="Size")

# Add threshold + percentile lines
plt.axhline(y=2.36, color='red', linestyle='--', label="Infrequent Threshold (2.36)")
plt.axhline(y=median, color='green', linestyle='--', label=f"Median ({median:.2f})")
plt.axhline(y=q3, color='orange', linestyle='--', label=f"75th Percentile ({q3:.2f})")

# Labels and layout
plt.title("Average Weekday Commits by Project Size")
plt.suptitle("")
plt.ylabel("Commits per Weekday")
plt.ylim(0, 3)
plt.legend()
plt.tight_layout()
plt.savefig("data/4_avg_commit_frequency_by_size.png", dpi=300, bbox_inches='tight')
