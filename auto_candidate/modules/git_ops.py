import os
import shutil
from git import Repo, GitCommandError
from rich.console import Console

console = Console()

class GitOperations:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir

    def clone_repo(self, repo_url: str, folder_name: str = "target_repo") -> str:
        """
        Clones a repository into the workspace.
        Returns the absolute path to the cloned repo.
        """
        target_path = os.path.join(self.workspace_dir, folder_name)

        if os.path.exists(target_path):
            console.print(f"[yellow]Target directory {target_path} already exists. Cleaning up...[/yellow]")
            shutil.rmtree(target_path)

        try:
            console.print(f"[cyan]Cloning {repo_url}...[/cyan]")
            Repo.clone_from(repo_url, target_path)
            console.print(f"[green]✔ Repository cloned to {target_path}[/green]")
            return target_path
        except GitCommandError as e:
            console.print(f"[bold red]Failed to clone repository:[/bold red] {e}")
            raise

    def copy_repo(self, local_path: str, folder_name: str = "target_repo") -> str:
        """
        Copies a local directory into the workspace.
        Returns the absolute path to the copied repo.
        """
        target_path = os.path.join(self.workspace_dir, folder_name)
        
        if os.path.exists(target_path):
            console.print(f"[yellow]Target directory {target_path} already exists. Cleaning up...[/yellow]")
            shutil.rmtree(target_path)
            
        try:
            console.print(f"[cyan]Copying local project from {local_path}...[/cyan]")
            # ignore .git to avoid copying huge history or config conflicts, 
            # we will re-init git if needed or we can copy it. 
            # Usually for a sandbox, copying .git is risky if we want a clean slate, 
            # but usually required if we want to branch off existing history.
            # Let's copy everything.
            shutil.copytree(local_path, target_path, symlinks=True, dirs_exist_ok=True)
            
            # Ensure it's a git repo so our branching logic works
            if not os.path.exists(os.path.join(target_path, ".git")):
                console.print("[dim]Initializing new git repository...[/dim]")
                repo = Repo.init(target_path)
                repo.git.add(all=True)
                repo.index.commit("Initial commit from local files")
            
            console.print(f"[green]✔ Project copied to {target_path}[/green]")
            return target_path
        except Exception as e:
            console.print(f"[bold red]Failed to copy local repository:[/bold red] {e}")
            raise

    def create_branch(self, repo_path: str, branch_name: str):
        """Creates and switches to a new branch."""
        try:
            repo = Repo(repo_path)
            current = repo.active_branch
            
            # Check if branch exists
            if branch_name in repo.heads:
                console.print(f"[yellow]Branch {branch_name} exists. Switching to it...[/yellow]")
                new_branch = repo.heads[branch_name]
            else:
                console.print(f"[cyan]Creating branch {branch_name} from {current.name}...[/cyan]")
                new_branch = repo.create_head(branch_name)
            
            new_branch.checkout()
            console.print(f"[green]✔ Checked out {branch_name}[/green]")
        except Exception as e:
            console.print(f"[red]Error managing branches: {e}[/red]")
            raise
