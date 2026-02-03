import typer
import os
from git import Repo
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from modules.prerequisites import PrerequisiteChecker
from modules.git_ops import GitOperations

app = typer.Typer()
console = Console()

@app.command()
def start(
    prompt_file: str = typer.Argument(..., help="Path to the take-home prompt file (or filename if using --local-path)"),
    repo_url: Optional[str] = typer.Option(None, help="The URL of the Github repository to clone"),
    local_path: Optional[str] = typer.Option(None, help="Path to a local directory to use instead of a remote repo"),
    workspace: str = typer.Option("./workspace", help="Directory where the project will be built"),
    versions: int = typer.Option(2, help="Number of solution versions to attempt"),
    model: str = typer.Option(None, help="Gemini model to use (e.g. gemini-1.5-flash). Skips interactive selection.")
):
    """
    AutoCandidate: Automated Take-Home Challenge Solver
    """
    console.print(Panel.fit("[bold blue]AutoCandidate[/bold blue]\nAutomated Take-Home Challenge Assistant"))

    if not repo_url and not local_path:
        console.print("[bold red]Error: You must provide either --repo-url or --local-path.[/bold red]")
        raise typer.Exit(code=1)

    if repo_url and local_path:
        console.print("[bold red]Error: Please provide only one of --repo-url or --local-path, not both.[/bold red]")
        raise typer.Exit(code=1)

    # 1. Prerequisites Check
    checker = PrerequisiteChecker()
    api_key = checker.check_api_key()
    if not checker.check_docker():
        console.print("[yellow]Warning: Docker check failed. Continuing, but build/test steps might fail.[/yellow]")

    # 2. Setup Workspace
    abs_workspace = os.path.abspath(workspace)
    if not os.path.exists(abs_workspace):
        os.makedirs(abs_workspace)
    
    # 3. Setup Project Source (Clone or Copy)
    git_ops = GitOperations(abs_workspace)
    repo_path = ""
    
    try:
        if repo_url:
            repo_path = git_ops.clone_repo(repo_url)
            # When cloning, prompt_file is expected to be a path provided by user
            final_prompt_path = prompt_file
        else:
            # Local path mode
            abs_local_path = os.path.abspath(local_path)
            if not os.path.exists(abs_local_path):
                console.print(f"[bold red]Local path not found: {abs_local_path}[/bold red]")
                raise typer.Exit(code=1)
                
            repo_path = git_ops.copy_repo(abs_local_path)
            
            # Resolve prompt file
            if os.path.isabs(prompt_file) or os.path.dirname(prompt_file):
                final_prompt_path = prompt_file
            else:
                final_prompt_path = os.path.join(repo_path, prompt_file)
                
    except Exception:
        raise typer.Exit(code=1)

    # 4. Verify Prompt File
    if not os.path.exists(final_prompt_path):
        console.print(f"[bold red]Prompt file not found: {final_prompt_path}[/bold red]")
        raise typer.Exit(code=1)

    with open(final_prompt_path, "r") as f:
        prompt_text = f.read()

    console.print(f"[green]✔ Setup complete. Ready to analyze {repo_path}[/green]")

    # --- PHASE 2: ANALYSIS & PLANNING ---
    console.print(Panel("[bold]Phase 2: Analysis & Planning[/bold]", border_style="blue"))
    
    from modules.inspector import ContextBuilder
    from modules.llm_engine import GeminiPlanner

    # Model Selection
    selected_model = model
    if not selected_model:
        available_models = GeminiPlanner.list_available_models(api_key)
        
        if not available_models:
            console.print("[red]No Gemini models found available for your key.[/red]")
            raise typer.Exit(code=1)

        console.print("\n[bold cyan]Available Gemini Models:[/bold cyan]")
        for idx, name in enumerate(available_models, 1):
            console.print(f"{idx}. {name}")
        
        choice = typer.prompt("\nSelect a model number", type=int, default=1)
        if 1 <= choice <= len(available_models):
            selected_model = available_models[choice - 1]
        else:
            console.print("[red]Invalid selection. Defaulting to first model.[/red]")
            selected_model = available_models[0]
        
    console.print(f"[green]Using model: {selected_model}[/green]\n")

    # Build Context
    console.print("[cyan]Analyzing codebase structure...[/cyan]")
    builder = ContextBuilder(repo_path)
    context_str = builder.get_context_string()
    
    # Generate Plans
    planner = GeminiPlanner(api_key=api_key, model_name=selected_model)
    plans = planner.generate_plans(prompt_text, context_str, num_versions=versions)

    if not plans:
        console.print("[red]Failed to generate plans. Exiting.[/red]")
        raise typer.Exit(code=1)

    # Save and Display Plans
    for i, plan_content in enumerate(plans, 1):
        plan_file = os.path.join(abs_workspace, f"plan_v{i}.txt")
        with open(plan_file, "w") as f:
            f.write(plan_content)
        
        console.print(Panel(f"Plan v{i} saved to {plan_file}", title=f"Strategy {i}", border_style="green"))
        # Briefly show the first few lines of the plan
        summary = "\n".join(plan_content.splitlines()[:10]) + "\n..."
        console.print(f"[dim]{summary}[/dim]")

    console.print(f"[bold green]✔ Planning complete. Generated {len(plans)} strategies.[/bold green]")

    # --- PHASE 3: EXECUTION ---
    console.print(Panel("[bold]Phase 3: Automated Implementation[/bold]", border_style="magenta"))
    from modules.coder import FilePatcher
    from modules.quality import QualityGate

    patcher = FilePatcher(abs_workspace)
    gate = QualityGate()
    
    # Detect default branch (usually main or master)
    try:
        repo = Repo(repo_path)
        default_branch = repo.active_branch.name
    except:
        default_branch = "main"

    results = []

    for i, plan_content in enumerate(plans, 1):
        version_name = f"solution-v{i}"
        console.print(f"\n[bold cyan]=== Implementing Version {i}: {version_name} ===[/bold cyan]")
        
        # 1. Reset to clean state
        try:
            repo.git.checkout(default_branch)
            git_ops.create_branch(repo_path, version_name)
        except Exception as e:
            console.print(f"[red]Git Error: {e}[/red]")
            continue

        # 2. Generate Code
        code_response = planner.generate_code(plan_content, context_str)
        if not code_response:
            console.print(f"[red]Skipping {version_name} due to generation failure.[/red]")
            continue
            
        # 3. Apply Code
        modified = patcher.apply_patches(code_response)
        console.print(f"[green]✔ Applied {len(modified)} files to branch {version_name}[/green]")
        
        # 4. Verification
        gate.install_dependencies(repo_path)
        test_success, test_log = gate.run_tests(repo_path)
        lint_success, lint_log = gate.run_linter(repo_path)
        
        results.append({
            "version": version_name,
            "tests": "PASS" if test_success else "FAIL",
            "lint": "PASS" if lint_success else "WARN",
            "files_changed": len(modified)
        })

    # --- PHASE 4: SUMMARY REPORT ---
    console.print("\n")
    console.print(Panel("[bold]Final Report[/bold]", border_style="green"))
    
    from rich.table import Table
    table = Table(title="Solution Candidates")
    table.add_column("Branch", style="cyan")
    table.add_column("Files Changed", justify="right")
    table.add_column("Tests", style="bold")
    table.add_column("Linting", style="bold")
    
    for res in results:
        test_style = "green" if res["tests"] == "PASS" else "red"
        lint_style = "green" if res["lint"] == "PASS" else "yellow"
        table.add_row(
            res["version"], 
            str(res["files_changed"]),
            f"[{test_style}]{res['tests']}[/{test_style}]", 
            f"[{lint_style}]{res['lint']}[/{lint_style}]"
        )
    
    consola.print(table)
    console.print(f"[dim]To review a solution: cd {workspace} && git checkout solution-v1[/dim]")


if __name__ == "__main__":
    app()