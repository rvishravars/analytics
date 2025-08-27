# Foundation Model CI/CD Analysis

This project is a collection of Python scripts designed to analyze various aspects of "CI Theater" in foundation model projects on GitHub. The scripts fetch data using the GitHub API and by cloning repositories, analyze metrics related to code size, testing, CI/CD usage, and commit patterns, and then generate reports and visualizations.

## Prerequisites

Before you begin, ensure you have the following installed:

*   Python 3.8+
*   Git
*   [cloc](https://github.com/AlDanial/cloc) (This command-line tool is required for the `2-ci-theater-project-size.py` script).

You will also need a GitHub Personal Access Token with `repo` scope to use the GitHub API for data collection.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/Foundation-model-ci-statistics.git
    cd Foundation-model-ci-statistics
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required Python packages:**
    This step will install all the necessary libraries listed in `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your environment variables:**
    Create a file named `.env` in the root of the project directory and add your GitHub token to it. This keeps your token secure and out of the source code.
    ```
    GITHUB_TOKEN="your_github_personal_access_token_here"
    ```
    The scripts will automatically load this token.

## Usage

The analysis scripts are located in the root directory and are numbered for a suggested execution order. They generate CSV files in the `data/` directory, which must exist before running the scripts.

To run a script:
```bash
python <script_name>.py
```

For example, to gather the initial project statistics:
```bash
python 1-github-project-statistics.py
```
