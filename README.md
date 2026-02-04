# AutoCandidate

AutoCandidate is an autonomous CLI agent designed to solve take-home coding challenges. It leverages the Gemini API to plan, architect, and implement solutions in a parallelized, task-based workflow.

## Key Features

*   **Autonomous Planning**: Analyzes the codebase and prompt to generate a comprehensive Master Implementation Plan and detailed Task Specifications.
*   **Parallel Execution**: Breaks down the solution into independent tasks and executes them simultaneously in isolated Git worktrees.
*   **Context-Aware Coding**: Each coding agent works with full awareness of the overall architecture and specific task requirements.
*   **Automated Conflict Resolution**: Intelligently resolves git merge conflicts using LLM reasoning during the integration phase.
*   **Self-Healing**: If integration tests fail, the system iteratively attempts to fix the code by analyzing error logs.
*   **Verification**: Performs a final semantic verification of the solution against the original requirements.

## Prerequisites

*   **Python 3.10+**
*   **Docker**: Required for running tests in a consistent environment (optional but recommended).
*   **Git**: Must be installed and configured.
*   **Gemini API Key**: You need a valid API key from Google AI Studio.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd auto_candidate
    ```

2.  **Run the setup script:**
    ```bash
    chmod +x setup.sh
    ./setup.sh
    ```

3.  **Configure Environment:**
    Create a `.env` file in the `auto_candidate` directory or export the variable:
    ```bash
    export GEMINI_API_KEY="your_api_key_here"
    ```

## Usage

The main entry point is `main.py`. You can run it using the virtual environment created by the setup script.

### basic Usage

To solve a challenge defined in `prompt.md` using a local repository:

```bash
source venv/bin/activate
python auto_candidate/main.py start prompt.md --local-path /path/to/challenge/repo
```

To solve a challenge from a remote Git URL:

```bash
source venv/bin/activate
python auto_candidate/main.py start prompt.md --repo-url https://github.com/username/challenge-repo.git
```

### Options

*   `--workspace`: Directory where the project will be built (default: `./workspace`).
*   `--model`: Specify a Gemini model (e.g., `gemini-1.5-pro`) to skip interactive selection.

## Output Artifacts

The tool generates several artifacts in your specified workspace:

*   `MASTER_PLAN.md`: High-level architectural plan.
*   `PLAN_<task_id>.md`: Detailed specifications for each task.
*   `VERIFICATION_REPORT.md`: Final analysis of the solution against requirements.
*   `FAILURE_REPORT.md`: (If applicable) Log of unresolvable errors for manual review.
