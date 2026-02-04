import typer
import os
import signal
import sys
import concurrent.futures
import json
from git import Repo
from typing import Optional, Dict, Any, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from dotenv import load_dotenv
from modules.prerequisites import PrerequisiteChecker
from modules.git_ops import GitOperations
from modules.inspector import ContextBuilder
from modules.llm_engine import GeminiPlanner
from modules.providers.base_provider import BaseLLMProvider
from modules.providers.gemini_provider import GeminiProvider
from modules.providers.claude_provider import ClaudeProvider
from modules.coder import FilePatcher
from modules.quality import QualityGate
from modules.checkpoint import CheckpointManager, calculate_prompt_hash
from modules.json_utils import extract_json_from_response

app = typer.Typer()
console = Console()

# Global context for interrupt handling
interrupt_context = {
    "checkpoint": None,
    "current_phase": None,
    "phase_state": None,
    "interrupted": False
}


def signal_handler(signum, frame):
    """Handle Ctrl-C interrupt gracefully by saving checkpoint."""
    if interrupt_context["interrupted"]:
        # Second Ctrl-C, force exit
        console.print("\n[bold red]Force exit. Checkpoint may not be saved.[/bold red]")
        sys.exit(1)

    interrupt_context["interrupted"] = True
    console.print("\n[yellow]Interrupt received. Saving checkpoint...[/yellow]")

    checkpoint = interrupt_context.get("checkpoint")
    current_phase = interrupt_context.get("current_phase")
    phase_state = interrupt_context.get("phase_state")

    if checkpoint and current_phase is not None and phase_state:
        try:
            # Determine which phase to save
            # If we're in Phase 3 and have partial results, save Phase 3 checkpoint
            # Otherwise, save the last completed phase (current_phase - 1)
            if current_phase == 3 and "phase_3_state" in phase_state:
                # Check if we have any completed tasks
                task_results = phase_state.get("phase_3_state", {}).get("task_results", [])
                if task_results:
                    console.print(f"[cyan]Cleaning up worktrees for completed tasks...[/cyan]")
                    # Clean up worktrees for completed tasks
                    workspace = interrupt_context.get("workspace")
                    repo_path = interrupt_context.get("repo_path")
                    if workspace and repo_path:
                        git_ops = GitOperations(workspace)
                        for res in task_results:
                            task_id = res["id"]
                            worktree_path = os.path.join(workspace, f"worktree-{task_id}")
                            try:
                                git_ops.cleanup_worktree(repo_path, worktree_path)
                            except Exception as e:
                                console.print(f"[dim]Warning: Failed to cleanup worktree for {task_id}: {e}[/dim]")

                    # Mark partial completion for resume
                    for res in task_results:
                        res["completed"] = True
                    checkpoint.save_checkpoint(3, phase_state)
                    console.print(f"[green]Checkpoint saved for Phase 3 (partial: {len(task_results)} tasks completed)[/green]")
                elif current_phase > 1:
                    checkpoint.save_checkpoint(current_phase - 1, phase_state)
                    console.print(f"[green]Checkpoint saved for Phase {current_phase - 1}[/green]")
            elif current_phase > 1:
                checkpoint.save_checkpoint(current_phase - 1, phase_state)
                console.print(f"[green]Checkpoint saved for Phase {current_phase - 1}[/green]")

            console.print("[cyan]You can resume with --resume flag[/cyan]")
        except Exception as e:
            console.print(f"[red]Failed to save checkpoint: {e}[/red]")

    console.print("[yellow]Exiting...[/yellow]")
    sys.exit(0)


def create_provider(provider_name: str, api_key: str, model_name: str) -> BaseLLMProvider:
    """Factory to create provider instances."""
    if provider_name == "gemini":
        return GeminiProvider(api_key, model_name)
    elif provider_name == "claude":
        return ClaudeProvider(api_key, model_name)
    else:
        raise ValueError(f"Unknown provider: {provider_name}. Supported: gemini, claude")


def display_resume_status(checkpoint_data: dict):
    """Display detailed resume status"""
    console.print("\n[bold cyan]Resume Status:[/bold cyan]")

    current_phase = checkpoint_data["current_phase"]
    phases_completed = checkpoint_data.get("phases_completed", [])

    table = Table(title="Checkpoint Status")
    table.add_column("Phase", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details")

    # Phase 1
    status_1 = "✓ Completed" if 1 in phases_completed else "⧗ In Progress"
    table.add_row("1. Initialization", status_1, checkpoint_data.get("workspace", ""))

    # Phase 2
    if 2 in phases_completed:
        phase_2 = checkpoint_data.get("phase_2_state", {})
        num_tasks = len(phase_2.get("plan_data", {}).get("tasks", []))
        status_2 = "✓ Completed"
        details_2 = f"{num_tasks} tasks planned"
    else:
        status_2 = "⧗ In Progress" if current_phase == 2 else "○ Pending"
        details_2 = ""
    table.add_row("2. Planning", status_2, details_2)

    # Phase 3
    if 3 in phases_completed:
        phase_3 = checkpoint_data.get("phase_3_state", {})
        results = phase_3.get("task_results", [])
        completed = sum(1 for r in results if r.get("completed"))
        failed = sum(1 for r in results if r.get("status") == "ERROR")
        status_3 = "✓ Completed"
        details_3 = f"{completed} tasks completed, {failed} failed"
    else:
        status_3 = "⧗ In Progress" if current_phase == 3 else "○ Pending"
        details_3 = ""
    table.add_row("3. Execution", status_3, details_3)

    # Phase 4
    if 4 in phases_completed:
        phase_4 = checkpoint_data.get("phase_4_state", {})
        tests_passed = phase_4.get("tests_passed", False)
        status_4 = "✓ Completed" if tests_passed else "✗ Failed"
        details_4 = "Tests passed" if tests_passed else "Tests failed"
    else:
        status_4 = "⧗ In Progress" if current_phase == 4 else "○ Pending"
        details_4 = ""
    table.add_row("4. Integration", status_4, details_4)

    console.print(table)
    console.print(f"\n[green]Will resume from Phase {current_phase + 1}[/green]\n")

def process_task(
    task: Dict[str, Any],
    base_repo_path: str,
    base_branch: str,
    workspace_dir: str,
    provider_name: str,
    api_key: str,
    model_name: str,
    context_str: str,
    plan_overview: str,
    task_spec: str
) -> Dict[str, Any]:
    """
    Executes a single task in its own git worktree.
    """
    task_id = task.get("id", "unknown")
    task_title = task.get("title", "Untitled")
    feature_branch = f"feat/{task_id}"
    worktree_path = os.path.join(workspace_dir, f"worktree-{task_id}")

    prefix = f"[{task_id}]"
    console.print(f"[cyan]{prefix} Starting: {task_title}...[/cyan]")

    try:
        git_ops = GitOperations(workspace_dir)

        # 1. Create Feature Branch
        repo = Repo(base_repo_path)
        if feature_branch not in repo.heads:
            base_commit = repo.heads[base_branch].commit
            repo.create_head(feature_branch, base_commit)
        else:
            repo.heads[feature_branch].set_commit(repo.heads[base_branch].commit)

        # 2. Setup Worktree
        git_ops.setup_worktree(base_repo_path, feature_branch, worktree_path)

        # 3. Generate Code
        provider = create_provider(provider_name, api_key, model_name)
        code_response = provider.execute_task(
            task,
            context_str,
            plan_overview=plan_overview,
            task_spec=task_spec
        )
        
        if not code_response:
            console.print(f"[red]{prefix} Code generation failed.[/red]")
            return {
                "id": task_id,
                "status": "FAILED",
                "branch": feature_branch,
                "error": "LLM Gen Failed"
            }

        # 4. Apply Code
        patcher = FilePatcher(worktree_path)
        modified = patcher.apply_patches(code_response)
        console.print(f"[green]{prefix} Applied {len(modified)} files[/green]")
        
        if not modified:
             console.print(f"[yellow]{prefix} No files modified.[/yellow]")

        # 5. Local Verification
        gate = QualityGate()
        lint_success, _ = gate.run_linter(worktree_path)
        
        # Commit
        if modified:
            wt_repo = Repo(worktree_path)
            wt_repo.git.add(all=True)
            wt_repo.index.commit(f"Implement {task_title}")
            console.print(f"[green]{prefix} Committed changes[/green]")

        return {
            "id": task_id,
            "status": "SUCCESS" if lint_success else "WARN",
            "branch": feature_branch,
            "files_changed": len(modified),
            "lint": lint_success
        }

    except Exception as e:
        console.print(f"[bold red]{prefix} Critical Error: {e}[/bold red]")
        return {
            "id": task_id,
            "status": "ERROR",
            "branch": feature_branch,
            "error": str(e)
        }

@app.command()
def start(
    prompt_file: str = typer.Argument(..., help="Path to the take-home prompt file (or filename if using --local-path)"),
    repo_url: Optional[str] = typer.Option(None, help="The URL of the Github repository to clone"),
    local_path: Optional[str] = typer.Option(None, help="Path to a local directory to use instead of a remote repo"),
    workspace: str = typer.Option("./workspace", help="Directory where the project will be built"),
    versions: int = typer.Option(1, help="Number of solution versions (Ignored in task mode, default 1)"),
    model: str = typer.Option(None, help="Model to use. Skips interactive selection."),
    planning_agent: str = typer.Option("gemini", help="Agent for planning phase: gemini or claude"),
    execution_agent: str = typer.Option("gemini", help="Agent for execution phase: gemini or claude"),
    integration_agent: str = typer.Option("gemini", help="Agent for integration phase: gemini or claude"),
    verification_agent: str = typer.Option("gemini", help="Agent for verification phase: gemini or claude"),
    resume: bool = typer.Option(False, help="Resume from previous checkpoint if available"),
):
    """
    AutoCandidate: Task-Based Parallel Solver
    """
    console.print(Panel.fit("[bold blue]AutoCandidate[/bold blue]\nTask-Based Parallel Solver"))

    # Register signal handler for graceful interrupt
    signal.signal(signal.SIGINT, signal_handler)

    # Load environment variables from .env file if it exists
    load_dotenv()

    # ... Setup ...
    if not repo_url and not local_path:
        console.print("[bold red]Error: You must provide either --repo-url or --local-path.[/bold red]")
        raise typer.Exit(code=1)
    if repo_url and local_path:
        console.print("[bold red]Error: Please provide only one.[/bold red]")
        raise typer.Exit(code=1)

    # Check API keys based on which agents are being used
    agents_used = {planning_agent, execution_agent, integration_agent, verification_agent}

    gemini_key = None
    claude_key = None

    if "gemini" in agents_used:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            console.print("[bold red]Error: GEMINI_API_KEY environment variable not set[/bold red]")
            console.print("Gemini agent is selected but API key is missing.")
            raise typer.Exit(1)

    if "claude" in agents_used:
        claude_key = os.getenv("ANTHROPIC_API_KEY")
        if not claude_key:
            console.print("[bold red]Error: ANTHROPIC_API_KEY environment variable not set[/bold red]")
            console.print("Claude agent is selected but API key is missing.")
            raise typer.Exit(1)

    # For backward compatibility, set api_key to gemini_key if available
    api_key = gemini_key or claude_key

    checker = PrerequisiteChecker()
    if not checker.check_docker():
        console.print("[yellow]Warning: Docker check failed.[/yellow]")

    abs_workspace = os.path.abspath(workspace)
    if not os.path.exists(abs_workspace):
        os.makedirs(abs_workspace)

    # Initialize checkpoint manager
    checkpoint = CheckpointManager(abs_workspace)

    # Initialize interrupt context for graceful shutdown
    interrupt_context["checkpoint"] = checkpoint
    interrupt_context["current_phase"] = 1
    interrupt_context["phase_state"] = {}
    interrupt_context["workspace"] = abs_workspace

    git_ops = GitOperations(abs_workspace)
    repo_path = ""
    try:
        if repo_url:
            repo_path = git_ops.clone_repo(repo_url)
            final_prompt_path = prompt_file
        else:
            abs_local_path = os.path.abspath(local_path)
            if not os.path.exists(abs_local_path):
                console.print(f"[bold red]Local path not found: {abs_local_path}[/bold red]")
                raise typer.Exit(1)
            repo_path = git_ops.copy_repo(abs_local_path)
            if os.path.isabs(prompt_file) or os.path.dirname(prompt_file):
                final_prompt_path = prompt_file
            else:
                final_prompt_path = os.path.join(repo_path, prompt_file)
    except Exception:
        raise typer.Exit(1)

    # Update interrupt context with repo path
    interrupt_context["repo_path"] = repo_path

    if not os.path.exists(final_prompt_path):
        console.print(f"[bold red]Prompt file not found: {final_prompt_path}[/bold red]")
        raise typer.Exit(1)

    with open(final_prompt_path, "r") as f:
        prompt_text = f.read()

    # Calculate prompt hash for checkpoint validation
    prompt_hash = calculate_prompt_hash(final_prompt_path)

    # Check for existing checkpoint and handle resume
    resume_from_phase = 1
    checkpoint_data = None

    if resume and checkpoint.checkpoint_exists():
        console.print("[cyan]Found existing checkpoint. Loading...[/cyan]")
        checkpoint_data = checkpoint.load_checkpoint()

        # Validate checkpoint
        if checkpoint.validate_checkpoint(prompt_hash, abs_workspace, repo_path):
            current_phase = checkpoint.get_current_phase()
            resume_from_phase = current_phase + 1
            display_resume_status(checkpoint_data)
        else:
            console.print("[red]Checkpoint validation failed. Starting fresh.[/red]")
            checkpoint.clear_checkpoint()
            checkpoint_data = None
    elif checkpoint.checkpoint_exists() and not resume:
        console.print("[yellow]Checkpoint exists but --resume not specified. Starting fresh.[/yellow]")

    # Handle Phase 1: Initialization (always load config, but might skip repo setup)
    if resume_from_phase > 1 and checkpoint_data:
        # Load configuration from checkpoint
        config = checkpoint_data.get("configuration", {})
        if not model:
            model = config.get("selected_model")
        console.print("[dim]Phase 1: Loaded from checkpoint[/dim]")
    else:
        # Save Phase 1 checkpoint
        phase_1_state = {
            "workspace": abs_workspace,
            "repo_path": repo_path,
            "prompt_file": final_prompt_path,
            "prompt_hash": prompt_hash,
            "prompt_text": prompt_text,
            "configuration": {
                "selected_model": model,
                "planning_agent": planning_agent,
                "execution_agent": execution_agent,
                "integration_agent": integration_agent,
                "verification_agent": verification_agent
            }
        }
        checkpoint.save_checkpoint(1, phase_1_state)
        interrupt_context["phase_state"] = phase_1_state

    # --- PHASE 2: PLANNING ---
    interrupt_context["current_phase"] = 2
    if resume_from_phase <= 2:
        console.print(Panel("[bold]Phase 2: Task Breakdown & Documentation[/bold]", border_style="blue"))
        console.print(f"[dim]Planning agent: {planning_agent}[/dim]")

        # Model Selection
        selected_model = model
        if not selected_model:
            # Get appropriate API key for planning agent
            planning_api_key = gemini_key if planning_agent == "gemini" else claude_key

            # Get available models from planning provider
            if planning_agent == "gemini":
                available_models = GeminiProvider.list_available_models(planning_api_key)
                provider_name = "Gemini"
            else:
                available_models = ClaudeProvider.list_available_models(planning_api_key)
                provider_name = "Claude"

            if not available_models:
                console.print(f"[red]No {provider_name} models found available.[/red]")
                raise typer.Exit(code=1)

            console.print(f"\n[bold cyan]Available {provider_name} Models:[/bold cyan]")
            for idx, name in enumerate(available_models, 1):
                console.print(f"{idx}. {name}")

            choice = typer.prompt("\nSelect a model number", type=int, default=1)
            if 1 <= choice <= len(available_models):
                selected_model = available_models[choice - 1]
            else:
                console.print("[red]Invalid selection. Defaulting to first model.[/red]")
                selected_model = available_models[0]

        console.print(f"[green]Using model: {selected_model}[/green]\n")

        builder = ContextBuilder(repo_path)
        context_str = builder.get_context_string()

        # Create planning provider
        planning_api_key = gemini_key if planning_agent == "gemini" else claude_key
        planner = create_provider(planning_agent, planning_api_key, selected_model)

        plan_data = planner.create_task_breakdown(prompt_text, context_str)
        tasks = plan_data.get("tasks", [])
        plan_overview = plan_data.get("plan_overview", "")

        if not tasks:
            console.print("[red]Failed to generate valid tasks. Exiting.[/red]")
            raise typer.Exit(1)

        master_doc = planner.create_master_plan_doc(plan_data, context_str)

        sub_plan_docs = {}
        for t in tasks:
            doc = planner.create_task_spec_doc(t, master_doc, context_str)
            sub_plan_docs[t["id"]] = doc

        review_result = planner.review_and_refine_plan(plan_data, master_doc, sub_plan_docs)
        if review_result != "OK":
            console.print("[yellow]Plan refinement triggered by Architect...[/yellow]")
            try:
                new_plan_data = extract_json_from_response(review_result)
                if new_plan_data:
                    tasks = new_plan_data.get("tasks", [])
                    plan_overview = new_plan_data.get("plan_overview", plan_overview)
                    console.print(f"[green]Plan refined. New task count: {len(tasks)}[/green]")
                else:
                    console.print(f"[red]Failed to parse refined plan. Reverting to original.[/red]")
            except Exception as e:
                console.print(f"[red]Error processing refined plan: {e}. Reverting to original.[/red]")

        with open(os.path.join(abs_workspace, "MASTER_PLAN.md"), "w") as f:
            f.write(master_doc)

        for t_id, doc in sub_plan_docs.items():
            clean_id = "".join(c for c in t_id if c.isalnum() or c in ('-','_'))
            with open(os.path.join(abs_workspace, f"PLAN_{clean_id}.md"), "w") as f:
                f.write(doc)

        console.print(f"\n[bold]Plan Overview:[/bold] {plan_overview}\n")
        task_table = Table(title="Execution Tasks")
        task_table.add_column("ID", style="cyan")
        task_table.add_column("Task", style="bold")
        task_table.add_column("Target Files")
        for t in tasks:
            task_table.add_row(t.get("id"), t.get("title"), ", ".join(t.get("target_files", [])[:3]))
        console.print(task_table)

        # Save Phase 2 checkpoint
        phase_2_state = {
            "phase_2_state": {
                "plan_data": plan_data,
                "master_plan_file": "MASTER_PLAN.md",
                "task_spec_files": [f"PLAN_{t['id']}.md" for t in tasks],
                "selected_model": selected_model,
                "context_str_length": len(context_str)
            }
        }
        checkpoint.save_checkpoint(2, phase_2_state)
        interrupt_context["phase_state"] = phase_2_state
    else:
        # Load planning data from checkpoint
        console.print("[dim]Phase 2: Loading from checkpoint...[/dim]")
        phase_2_state = checkpoint_data["phase_2_state"]
        plan_data = phase_2_state["plan_data"]
        tasks = plan_data["tasks"]
        plan_overview = plan_data["plan_overview"]
        selected_model = phase_2_state["selected_model"]

        # Initialize builder for later use
        builder = ContextBuilder(repo_path)
        context_str = builder.get_context_string()

        # Read planning docs from disk
        with open(os.path.join(abs_workspace, "MASTER_PLAN.md")) as f:
            master_doc = f.read()

        sub_plan_docs = {}
        for t in tasks:
            clean_id = "".join(c for c in t["id"] if c.isalnum() or c in ('-','_'))
            plan_file = os.path.join(abs_workspace, f"PLAN_{clean_id}.md")
            with open(plan_file) as f:
                sub_plan_docs[t["id"]] = f.read()

        console.print(f"[green]Loaded {len(tasks)} tasks from checkpoint[/green]")

    # --- PHASE 3: EXECUTION ---
    interrupt_context["current_phase"] = 3
    if resume_from_phase <= 3:
        console.print(Panel(f"[bold]Phase 3: Parallel Execution ({len(tasks)} tasks)[/bold]", border_style="magenta"))
        console.print(f"[dim]Execution agent: {execution_agent}[/dim]")

        base_branch = "solution-v1"
        try:
            repo = Repo(repo_path)
            git_ops.create_branch(repo_path, base_branch)
        except Exception as e:
            console.print(f"[red]Git setup error: {e}[/red]")
            raise typer.Exit(1)

        # Handle partial resume: check which tasks already completed
        if resume_from_phase == 3 and checkpoint_data:
            phase_3_state = checkpoint_data.get("phase_3_state", {})
            previous_results = phase_3_state.get("task_results", [])
            completed_task_ids = {r["id"] for r in previous_results if r.get("completed")}

            # Filter tasks to only incomplete ones
            tasks_to_run = [t for t in tasks if t["id"] not in completed_task_ids]
            console.print(f"[cyan]Resuming execution: {len(completed_task_ids)} tasks already completed, {len(tasks_to_run)} remaining[/cyan]")

            # Start with previous results
            results = previous_results
        else:
            tasks_to_run = tasks
            results = []

        # Get API key for execution agent
        execution_api_key = gemini_key if execution_agent == "gemini" else claude_key

        # Execute remaining tasks
        if tasks_to_run:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks_to_run)) as executor:
                future_to_task = {
                    executor.submit(
                        process_task,
                        t,
                        repo_path,
                        base_branch,
                        abs_workspace,
                        execution_agent,
                        execution_api_key,
                        selected_model,
                        context_str,
                        master_doc,
                        sub_plan_docs.get(t["id"], "")
                    ): t
                    for t in tasks_to_run
                }

                for future in concurrent.futures.as_completed(future_to_task):
                    try:
                        data = future.result()
                        results.append(data)
                        # Update interrupt context with partial progress
                        interrupt_context["phase_state"] = {
                            "phase_3_state": {
                                "base_branch": base_branch,
                                "task_results": results
                            }
                        }
                    except Exception as exc:
                        console.print(f"[red]Task exception: {exc}[/red]")

        # Mark all results as completed for checkpoint tracking
        for res in results:
            res["completed"] = True

        # Clean up worktrees after all tasks complete
        console.print("[cyan]Cleaning up worktrees...[/cyan]")
        for res in results:
            task_id = res["id"]
            worktree_path = os.path.join(abs_workspace, f"worktree-{task_id}")
            try:
                git_ops.cleanup_worktree(repo_path, worktree_path)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to cleanup worktree for {task_id}: {e}[/yellow]")

        # Save Phase 3 checkpoint
        phase_3_state = {
            "phase_3_state": {
                "base_branch": base_branch,
                "task_results": results
            }
        }
        checkpoint.save_checkpoint(3, phase_3_state)
        interrupt_context["phase_state"] = phase_3_state
    else:
        # Load execution results from checkpoint
        console.print("[dim]Phase 3: Loading from checkpoint...[/dim]")
        phase_3_state = checkpoint_data["phase_3_state"]
        results = phase_3_state["task_results"]
        base_branch = phase_3_state["base_branch"]
        console.print(f"[green]Loaded {len(results)} task results from checkpoint[/green]")

        # Initialize repo for later use
        repo = Repo(repo_path)

        # Ensure base branch exists (create if needed for resume)
        try:
            # Check if branch exists
            repo.git.rev_parse('--verify', base_branch)
            console.print(f"[dim]Base branch '{base_branch}' exists[/dim]")
        except:
            # Branch doesn't exist, create it
            console.print(f"[yellow]Base branch '{base_branch}' not found, creating it...[/yellow]")
            git_ops.create_branch(repo_path, base_branch)

    # --- PHASE 4: MERGE & VERIFY ---
    interrupt_context["current_phase"] = 4
    console.print(Panel("[bold]Phase 4: Integration & Verification[/bold]", border_style="green"))
    console.print(f"[dim]Integration agent: {integration_agent}[/dim]")
    console.print(f"[dim]Verification agent: {verification_agent}[/dim]")

    # When resuming, ensure worktrees are cleaned up and branches are accessible
    if resume_from_phase == 4:
        console.print("[cyan]Verifying worktrees and branches...[/cyan]")
        for res in results:
            task_id = res["id"]
            worktree_path = os.path.join(abs_workspace, f"worktree-{task_id}")

            # Clean up any remaining worktrees
            if os.path.exists(worktree_path):
                console.print(f"[yellow]Found stale worktree for {task_id}, cleaning up...[/yellow]")
                try:
                    git_ops.cleanup_worktree(repo_path, worktree_path)
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to cleanup worktree for {task_id}: {e}[/yellow]")

            # Verify branch exists in main repo
            branch_name = res["branch"]
            try:
                repo.git.rev_parse('--verify', branch_name)
            except:
                console.print(f"[yellow]Warning: Branch {branch_name} not found in main repo[/yellow]")
                # Branch doesn't exist - this shouldn't happen after proper cleanup
                # Mark this result as failed so it won't be merged
                res["status"] = "ERROR"
                res["error"] = "Branch not found after cleanup"

    # Create integration provider for merge conflict resolution and fixing
    integration_api_key = gemini_key if integration_agent == "gemini" else claude_key
    integration_provider = create_provider(integration_agent, integration_api_key, selected_model)

    successful_tasks = [r for r in results if r["status"] in ["SUCCESS", "WARN"]]
    successful_tasks.sort(key=lambda x: x["id"])

    # Handle partial resume: check which branches already merged
    if resume_from_phase == 4 and checkpoint_data:
        phase_4_state = checkpoint_data.get("phase_4_state", {})
        merged_branches = set(phase_4_state.get("merged_branches", []))
        test_attempt_start = phase_4_state.get("test_attempt", 0)
        console.print(f"[cyan]Resuming integration: {len(merged_branches)} branches already merged[/cyan]")

        # Filter out already-merged branches
        tasks_to_merge = [r for r in successful_tasks if r["branch"] not in merged_branches]
    else:
        merged_branches = set()
        test_attempt_start = 0
        tasks_to_merge = successful_tasks

    # Merge remaining branches (check if they exist first)
    merge_success_count = len(merged_branches)
    for res in tasks_to_merge:
        branch_name = res["branch"]

        # Check if branch exists before attempting merge
        try:
            repo.git.rev_parse('--verify', branch_name)
            branch_exists = True
        except:
            branch_exists = False
            console.print(f"[yellow]Warning: Branch {branch_name} does not exist, skipping...[/yellow]")

        if branch_exists and git_ops.merge_feature_branch(
            repo_path,
            base_branch,
            branch_name,
            resolver=integration_provider,
            plan_context=master_doc
        ):
            merge_success_count += 1
            merged_branches.add(branch_name)

    console.print(f"\n[green]Merged {merge_success_count}/{len(successful_tasks)} feature branches into {base_branch}[/green]")

    # Final Verification Loop
    gate = QualityGate()
    repo_patcher = FilePatcher(repo_path)

    console.print("[cyan]Running Final Integration Tests...[/cyan]")
    gate.install_dependencies(repo_path)

    max_retries = 2
    tests_passed = False
    test_log = ""

    for attempt in range(max_retries + 1):
        success, output = gate.run_tests(repo_path)
        test_log = output

        if success:
            tests_passed = True
            break

        if attempt < max_retries:
            console.print(Panel(output[-1000:], title=f"[yellow]Tests Failed (Attempt {attempt+1}/{max_retries+1}). Fix requested...[/yellow]", border_style="yellow"))

            new_context = builder.get_context_string()
            fix_response = integration_provider.fix_code(output, prompt_text, new_context)
            
            if fix_response:
                try:
                    fixed_files = repo_patcher.apply_patches(fix_response)
                    if fixed_files:
                        console.print(f"[green]Applied fixes to {len(fixed_files)} files.[/green]")
                        repo.git.add(all=True)
                        repo.git.commit('-m', f"Auto-fix test failures (Attempt {attempt+1})")
                    else:
                        console.print("[red]LLM returned no fixes.[/red]")
                        break
                except Exception as e:
                    console.print(f"[red]Error applying fixes: {e}[/red]")
                    break
            else:
                console.print("[red]LLM failed to generate a fix.[/red]")
                break
        else:
            console.print("[bold red]Max retries reached. Tests still failing.[/bold red]")

    if not tests_passed:
        console.print(Panel(test_log, title="[bold red]Final Test Failures[/bold red]", border_style="red"))

        failure_report_path = os.path.join(abs_workspace, "FAILURE_REPORT.md")
        with open(failure_report_path, "w") as f:
            f.write(f"# AutoCandidate Failure Report\n\n## Test Output\n```\n{test_log}\n```\n")
        console.print(f"[yellow]Failure report saved to: {failure_report_path}[/yellow]")
        console.print("[bold red]Action Required: Please review the failures manually.[/bold red]")
    else:
        console.print("[bold green]All Tests Passed![/bold green]")

        # Create verification provider
        verification_api_key = gemini_key if verification_agent == "gemini" else claude_key
        verification_provider = create_provider(verification_agent, verification_api_key, selected_model)

        verify_report = verification_provider.verify_solution(prompt_text, builder.get_context_string(), test_log)
        verify_path = os.path.join(abs_workspace, "VERIFICATION_REPORT.md")
        with open(verify_path, "w") as f:
            f.write(verify_report)

        console.print(Panel(verify_report, title="Requirement Verification", border_style="blue"))
        console.print(f"[dim]Verification report saved to: {verify_path}[/dim]")

    # Save Phase 4 checkpoint
    checkpoint.save_checkpoint(4, {
        "phase_4_state": {
            "merged_branches": list(merged_branches),
            "test_attempt": max_retries + 1 if not tests_passed else 1,
            "tests_passed": tests_passed,
            "last_test_output": test_log
        }
    })

    console.print(f"[dim]Project located at: {repo_path}[/dim]")
    console.print(f"[dim]To inspect: cd {workspace}/target_repo && git checkout {base_branch}[/dim]")


@app.command()
def checkpoint_status(
    workspace: str = typer.Option("./workspace", help="Workspace directory")
):
    """Display checkpoint status without resuming"""
    abs_workspace = os.path.abspath(workspace)
    checkpoint = CheckpointManager(abs_workspace)

    if not checkpoint.checkpoint_exists():
        console.print("[yellow]No checkpoint found[/yellow]")
        return

    checkpoint_data = checkpoint.load_checkpoint()
    display_resume_status(checkpoint_data)


@app.command()
def checkpoint_clear(
    workspace: str = typer.Option("./workspace", help="Workspace directory")
):
    """Clear existing checkpoint"""
    abs_workspace = os.path.abspath(workspace)
    checkpoint = CheckpointManager(abs_workspace)

    if checkpoint.checkpoint_exists():
        checkpoint.clear_checkpoint()
        console.print("[green]Checkpoint cleared[/green]")
    else:
        console.print("[yellow]No checkpoint found[/yellow]")


@app.command()
def checkpoint_info(
    workspace: str = typer.Option("./workspace", help="Workspace directory")
):
    """Show detailed checkpoint information"""
    abs_workspace = os.path.abspath(workspace)
    checkpoint = CheckpointManager(abs_workspace)

    if not checkpoint.checkpoint_exists():
        console.print("[yellow]No checkpoint found[/yellow]")
        return

    checkpoint_data = checkpoint.load_checkpoint()
    console.print(json.dumps(checkpoint_data, indent=2))


if __name__ == "__main__":
    app()