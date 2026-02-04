# AutoCandidate

AutoCandidate is an autonomous CLI agent designed to solve take-home coding challenges. It leverages LLM APIs (Gemini and Claude Code) to plan, architect, and implement solutions in a parallelized, task-based workflow.

## Key Features

*   **Autonomous Planning**: Analyzes the codebase and prompt to generate a comprehensive Master Implementation Plan and detailed Task Specifications.
*   **Parallel Execution**: Breaks down the solution into independent tasks and executes them simultaneously in isolated Git worktrees.
*   **Context-Aware Coding**: Each coding agent works with full awareness of the overall architecture and specific task requirements.
*   **Automated Conflict Resolution**: Intelligently resolves git merge conflicts using LLM reasoning during the integration phase.
*   **Self-Healing**: If integration tests fail, the system iteratively attempts to fix the code by analyzing error logs.
*   **Verification**: Performs a final semantic verification of the solution against the original requirements.
*   **Multi-Agent Support**: Choose between Gemini and Claude Code for different phases of the workflow, optimizing for each agent's strengths.

## Prerequisites

*   **Python 3.10+**
*   **Docker**: Required for running tests in a consistent environment (optional but recommended).
*   **Git**: Must be installed and configured.
*   **LLM API Keys**: You need at least one of the following:
    *   **Gemini API Key**: From Google AI Studio (for Gemini agent)
    *   **Anthropic API Key**: From Anthropic Console (for Claude agent)

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
    Set API keys either via environment variables or a `.env` file.

    **Option 1: Using .env file (Recommended)**

    Create a `.env` file in the project root directory:
    ```bash
    # .env file
    GEMINI_API_KEY=your_gemini_api_key_here
    ANTHROPIC_API_KEY=your_anthropic_api_key_here
    ```

    **Option 2: Using environment variables**

    Export the variables in your shell:
    ```bash
    export GEMINI_API_KEY="your_gemini_api_key_here"
    export ANTHROPIC_API_KEY="your_anthropic_api_key_here"
    ```

    **Note:** The system will automatically load API keys from the `.env` file if it exists. You only need to set the API key(s) for the agent(s) you plan to use.

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
*   `--model`: Specify a model (e.g., `gemini-2.0-flash` or `claude-sonnet-4-5-20250929`) to skip interactive selection.
*   `--planning-agent`: Agent for planning phase: `gemini` or `claude` (default: `gemini`).
*   `--execution-agent`: Agent for execution phase: `gemini` or `claude` (default: `gemini`).
*   `--integration-agent`: Agent for integration phase: `gemini` or `claude` (default: `gemini`).
*   `--verification-agent`: Agent for verification phase: `gemini` or `claude` (default: `gemini`).

## Multi-Agent Support

AutoCandidate now supports using different LLM agents for different phases of the workflow. This allows you to leverage the strengths of each model:

### Use Claude for Everything

```bash
python auto_candidate/main.py start prompt.md \
  --local-path /path/to/repo \
  --planning-agent claude \
  --execution-agent claude \
  --integration-agent claude \
  --verification-agent claude
```

### Mix Agents (Recommended)

Use Gemini for planning and Claude for implementation:

```bash
python auto_candidate/main.py start prompt.md \
  --local-path /path/to/repo \
  --planning-agent gemini \
  --execution-agent claude \
  --integration-agent claude \
  --verification-agent gemini
```

### Use Gemini for Everything (Default)

If you don't specify agent options, the system defaults to using Gemini for all phases:

```bash
python auto_candidate/main.py start prompt.md --local-path /path/to/repo
```

### Required API Keys

The system will automatically check for the required API keys based on which agents you select:
- If using `gemini` for any phase: `GEMINI_API_KEY` must be set
- If using `claude` for any phase: `ANTHROPIC_API_KEY` must be set

## Output Artifacts

The tool generates several artifacts in your specified workspace:

*   `MASTER_PLAN.md`: High-level architectural plan.
*   `PLAN_<task_id>.md`: Detailed specifications for each task.
*   `VERIFICATION_REPORT.md`: Final analysis of the solution against requirements.
*   `FAILURE_REPORT.md`: (If applicable) Log of unresolvable errors for manual review.
