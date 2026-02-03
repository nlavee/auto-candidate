import subprocess
import os
from rich.console import Console

console = Console()

class QualityGate:
    def __init__(self):
        pass

    def _run_cmd(self, cmd: list, cwd: str) -> tuple[bool, str]:
        """Runs a shell command and returns (success, output)."""
        try:
            result = subprocess.run(
                cmd, 
                cwd=cwd, 
                capture_output=True, 
                text=True, 
                check=False
            )
            return (result.returncode == 0, result.stdout + "\n" + result.stderr)
        except Exception as e:
            return (False, str(e))

    def install_dependencies(self, repo_path: str):
        """Attempts to install dependencies from requirements.txt."""
        req_path = os.path.join(repo_path, "requirements.txt")
        if os.path.exists(req_path):
            console.print("[cyan]Installing project dependencies...[/cyan]")
            success, output = self._run_cmd(["pip", "install", "-r", "requirements.txt"], cwd=repo_path)
            if not success:
                console.print(f"[yellow]Warning: Dependency installation failed.\n{output[:200]}...[/yellow]")
        else:
            console.print("[dim]No requirements.txt found. Skipping install.[/dim]")

    def run_tests(self, repo_path: str) -> tuple[bool, str]:
        """Runs pytest."""
        console.print("[cyan]Running tests...[/cyan]")
        # We assume pytest is installed in the environment
        success, output = self._run_cmd(["pytest"], cwd=repo_path)
        if success:
            console.print("[green]✔ Tests Passed[/green]")
        else:
            console.print("[red]✘ Tests Failed[/red]")
        return success, output

    def run_linter(self, repo_path: str) -> tuple[bool, str]:
        """Runs ruff (fast linter) or pylint."""
        console.print("[cyan]Running linter (ruff)...[/cyan]")
        # Fallback to just basic python syntax check if ruff missing? 
        # For now, let's try ruff, assuming it's in our tool's venv.
        success, output = self._run_cmd(["ruff", "check", "."], cwd=repo_path)
        if success:
            console.print("[green]✔ Lint Passed[/green]")
        else:
            console.print("[yellow]⚠ Lint Issues Found[/yellow]")
        return success, output
