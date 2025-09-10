import pandas as pd
import matplotlib.pyplot as plt

# Load the two datasets
stats_df = pd.read_csv("data/23_github_projects_stats_rust.csv")
sizes_df = pd.read_csv("data/19_ci_theater_project_sizes_rust.csv")

print("Stats CSV columns:", stats_df.columns.tolist())
print("Sizes CSV columns:", sizes_df.columns.tolist())

# Merge based on project name
df = pd.merge(stats_df, sizes_df[["name", "Category"]], left_on="Project", right_on="name", how="inner")

# Rename for clarity
df = df.rename(columns={
    "Time to First CI (months)": "Time_To_First_CI",
    "Category": "Size",
})
df = df.drop(columns=["name"])  # Remove redundant 'name' column from the merge

# Convert 'Time_To_First_CI' to a numeric type, coercing errors into NaN
df["Time_To_First_CI"] = pd.to_numeric(df["Time_To_First_CI"], errors='coerce')

# Drop rows where 'Time_To_First_CI' is missing, as they cannot be plotted
df.dropna(subset=["Time_To_First_CI"], inplace=True)

if df.empty:
    print("\nError: No valid data to plot after merging and cleaning.")
    exit()

# Plot: Boxplot of time to first CI grouped by project size
plt.figure(figsize=(8, 5))
df.boxplot(column="Time_To_First_CI", by="Size")
plt.title("Time to First CI Adoption by Project Size")
plt.suptitle("")
plt.ylabel("Months from Repo Creation")
plt.tight_layout()
plt.savefig("data/25_time_to_first_ci_by_size_rust.png", dpi=300, bbox_inches="tight")
