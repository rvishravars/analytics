import os
import csv
import tempfile
import unittest
import pandas as pd

def categorize_project(sloc: int) -> str:
    """Categorizes a project based on its Rust SLOC."""
    if sloc < 10000:
        return "Small"
    elif sloc < 100000:
        return "Medium"
    else:
        return "Large"

def process_cohort(bugs_file: str, sizes_file: str, cohort_name: str):
    try:
        bugs_df = pd.read_csv(bugs_file)
        sizes_df = pd.read_csv(sizes_file)
    except FileNotFoundError as e:
        print(f"Error: Input file not found: {e.filename}")
        return None

    # Merge on project slug (bugs file uses "Project", sizes file uses "repo")
    df = pd.merge(bugs_df, sizes_df, left_on="Project", right_on="repo", how="inner")

    if df.empty:
        print(f"No data available for {cohort_name}.")
        return None

    # Compute bug ratio if sum of before+after > 0; else keep as None
    df["Total Bugs"] = df["Bug Issues Before CI"] + df["Bug Issues After CI"]
    df["Bug Ratio"] = df.apply(lambda row: row["Bug Issues After CI"] / row["Total Bugs"]
                               if row["Total Bugs"] > 0 else None, axis=1)
    
    # Add project size category based on rust_sloc
    df["Size Category"] = df["rust_sloc"].apply(categorize_project)
    size_order = ["Small", "Medium", "Large"]
    df["Size Category"] = pd.Categorical(df["Size Category"], categories=size_order, ordered=True)
    
    return df

class TestProcessCohort(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory to hold the CSV files.
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_path = self.test_dir.name

        # Prepare filepaths for valid test data
        self.bugs_file = os.path.join(self.test_path, "bugs.csv")
        self.sizes_file = os.path.join(self.test_path, "sizes.csv")

        # Write valid bugs CSV file
        with open(self.bugs_file, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Project", "Bug Issues Before CI", "Bug Issues After CI"])
            writer.writerow(["proj1", 10, 5])
            writer.writerow(["proj2", 0, 2])
        
        # Write valid sizes CSV file
        with open(self.sizes_file, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["repo", "rust_sloc"])
            writer.writerow(["proj1", 8000])
            writer.writerow(["proj2", 15000])
        
    def tearDown(self):
        # Clean up the temporary directory
        self.test_dir.cleanup()

    def test_valid_merge(self):
        """Test that process_cohort properly merges the CSV files and calculates fields."""
        df = process_cohort(self.bugs_file, self.sizes_file, "TestCohort")
        self.assertIsInstance(df, pd.DataFrame)
        # Check that merged dataframe has two rows
        self.assertEqual(len(df), 2)
        # Check required columns exist
        for col in ["Total Bugs", "Bug Ratio", "Size Category"]:
            self.assertIn(col, df.columns)
        # Validate computed Total Bugs and Bug Ratio for each project
        # For proj1: Total Bugs = 10 + 5 = 15, Bug Ratio = 5/15 = 0.3333...
        proj1 = df[df["Project"] == "proj1"].iloc[0]
        self.assertEqual(proj1["Total Bugs"], 15)
        self.assertAlmostEqual(proj1["Bug Ratio"], 5/15, places=4)
        # For proj2: Total Bugs = 0 + 2 = 2, Bug Ratio = 2/2 = 1.0
        proj2 = df[df["Project"] == "proj2"].iloc[0]
        self.assertEqual(proj2["Total Bugs"], 2)
        self.assertAlmostEqual(proj2["Bug Ratio"], 1.0, places=4)
        # Validate Size Category assignment based on rust_sloc
        # proj1: 8000 -> "Small"
        self.assertEqual(proj1["Size Category"], "Small")
        # proj2: 15000 -> "Medium"
        self.assertEqual(proj2["Size Category"], "Medium")

    def test_missing_file(self):
        """Test that process_cohort returns None if a file is missing."""
        missing_file = os.path.join(self.test_path, "nonexistent.csv")
        result = process_cohort(missing_file, self.sizes_file, "TestCohort")
        self.assertIsNone(result)
        result = process_cohort(self.bugs_file, missing_file, "TestCohort")
        self.assertIsNone(result)

    def test_empty_merge(self):
        """Test that process_cohort returns None when merging results in an empty dataframe."""
        # Create CSV files that will not merge (different keys)
        bugs_file = os.path.join(self.test_path, "bugs_no_match.csv")
        sizes_file = os.path.join(self.test_path, "sizes_no_match.csv")
        with open(bugs_file, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Project", "Bug Issues Before CI", "Bug Issues After CI"])
            writer.writerow(["projA", 5, 1])
        with open(sizes_file, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["repo", "rust_sloc"])
            writer.writerow(["projB", 20000])
        result = process_cohort(bugs_file, sizes_file, "TestCohort")
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()