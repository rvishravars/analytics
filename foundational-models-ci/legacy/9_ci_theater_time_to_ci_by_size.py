import pandas as pd
import matplotlib.pyplot as plt

# Load the two datasets
stats_df = pd.read_csv("data/1_github_projects_stats.csv")
sizes_df = pd.read_csv("data/2_ci_theater_project_sizes.csv")

print("Stats CSV columns:", stats_df.columns.tolist())
print("Sizes CSV columns:", sizes_df.columns.tolist())

# Merge based on project name
df = pd.merge(stats_df, sizes_df[["name", "Category"]], left_on="Project", right_on="name", how="inner")
df = df.rename(columns={
    "Time to First CI (months)": "Time_To_First_CI",
})
df = df.drop(columns=["name"])  # Remove duplicate name column

# Rename for clarity
df = df.rename(columns={
    "name": "Project",
    "ci_start_delay_months": "Time_To_First_CI",
    "Category": "Size"
})

# Drop missing or invalid values
df = df[df["Time_To_First_CI"].notna()]
df["Time_To_First_CI"] = pd.to_numeric(df["Time_To_First_CI"], errors="coerce")


# Plot: Boxplot of time to first CI grouped by project size
plt.figure(figsize=(8, 5))
df.boxplot(column="Time_To_First_CI", by="Size")
plt.title("Time to First CI Adoption by Project Size")
plt.suptitle("")
plt.ylabel("Months from Repo Creation")
plt.tight_layout()
plt.savefig("data/9_time_to_first_ci_by_size.png", dpi=300, bbox_inches="tight")
