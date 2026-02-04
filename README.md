# AutoCandidate

AutoCandidate is an autonomous CLI agent designed to solve take-home coding challenges. It leverages LLM APIs (Gemini and Claude Code) to plan, architect, and implement solutions in a parallelized, task-based workflow.

## Table of Contents

- [Quick Start](#quick-start)
- [Key Features](#key-features)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Usage](#usage)
  - [Interactive Mode](#interactive-mode-recommended)
  - [Direct Command Mode](#direct-command-mode)
- [Multi-Agent Support](#multi-agent-support)
- [Checkpoint and Resume](#checkpoint-and-resume)
- [Output Artifacts](#output-artifacts)

## Quick Start

Get started in 3 simple steps:

```bash
# 1. Run setup
./setup.sh

# 2. Configure API keys (create .env file)
echo "GEMINI_API_KEY=your_key_here" > .env
echo "ANTHROPIC_API_KEY=your_key_here" >> .env

# 3. Run the interactive tool
./run.sh
```

That's it! The interactive runner will guide you through the rest.

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

4.  **Start using AutoCandidate:**

    Run the interactive tool:
    ```bash
    ./run.sh
    ```

    Or use direct commands (see Usage section below).

## Usage

AutoCandidate provides two ways to run: an interactive mode (recommended for beginners) and direct command-line mode (for advanced users).

### Interactive Mode (Recommended)

The easiest way to get started is using the interactive runner:

```bash
./run.sh
```

This interactive script will guide you through:
- **Main Operations**: Start a new run, check checkpoint status, clear checkpoints, or view checkpoint details
- **Run Configuration**: Prompt file location, repository source (local/remote), workspace directory
- **Agent Selection**: Choose Gemini, Claude, or custom configuration for each phase
- **Resume Mode**: Automatically detect and resume from checkpoints
- **Model Selection**: Specify a model or select interactively
- **Smart Validation**: Checks for required files and API keys before running

### Direct Command Mode

For advanced users or scripting, you can run AutoCandidate directly:

**Using a local repository:**
```bash
source venv/bin/activate
python auto_candidate/main.py start prompt.md --local-path /path/to/challenge/repo
```

**Using a remote Git URL:**
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
*   `--resume`: Resume from previous checkpoint if available (default: `False`).

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

## Checkpoint and Resume

AutoCandidate supports checkpointing and resuming from failures. This is helpful for long-running tasks where you want to fix issues and continue without starting from scratch.

### How It Works

1. **Automatic Checkpoints**: The system automatically saves checkpoints after each phase completes
2. **Resume Mode**: Use `--resume` flag (or enable in interactive mode) to continue from the last checkpoint
3. **Manual Fixes**: You can make manual fixes between runs (edit code, fix planning docs, etc.)
4. **Validation**: Checkpoints are validated to ensure compatibility with the current run

### Usage Examples

**Using Interactive Mode (Easiest):**
```bash
./run.sh
# Select option 1 (Start), then answer 'y' when asked about resume mode
# Or select option 2, 3, or 4 for checkpoint management
```

**Using Direct Commands:**

**Start a new run (creates checkpoints automatically):**
```bash
python auto_candidate/main.py start prompt.md --local-path /path/to/repo
```

**Resume from last checkpoint after a failure:**
```bash
python auto_candidate/main.py start prompt.md --local-path /path/to/repo --resume
```

**Check checkpoint status:**
```bash
python auto_candidate/main.py checkpoint-status --workspace ./workspace
```

**Clear checkpoint (start fresh):**
```bash
python auto_candidate/main.py checkpoint-clear --workspace ./workspace
```

**View detailed checkpoint information:**
```bash
python auto_candidate/main.py checkpoint-info --workspace ./workspace
```

### What Can Be Resumed

- **After Phase 2**: Planning completed, continue to execution
- **During Phase 3**: Some tasks completed, continue with remaining tasks
- **After Phase 3**: All tasks completed, continue to integration/testing
- **During Phase 4**: Branches merged, continue with testing

### Example Workflow

1. Start a run that fails during execution:
   ```bash
   python auto_candidate/main.py start prompt.md --local-path /path/to/repo
   # ... Phase 3 fails on task_03 ...
   ```

2. Investigate the failure:
   ```bash
   cd workspace/worktree-task_03
   # Fix the code manually
   git add . && git commit -m "Manual fix"
   ```

3. Resume from checkpoint:
   ```bash
   python auto_candidate/main.py start prompt.md --local-path /path/to/repo --resume
   # Continues from Phase 3, skips completed tasks
   ```

### Checkpoint File Location

Checkpoints are stored in: `{workspace}/.autocandidate_checkpoint.json`

This file contains:
- Current phase and progress
- Configuration (agents, model)
- Task results and status
- Planning artifacts metadata

## Output Artifacts

The tool generates several artifacts in your specified workspace:

*   `MASTER_PLAN.md`: High-level architectural plan.
*   `PLAN_<task_id>.md`: Detailed specifications for each task.
*   `VERIFICATION_REPORT.md`: Final analysis of the solution against requirements.
*   `FAILURE_REPORT.md`: (If applicable) Log of unresolvable errors for manual review.
