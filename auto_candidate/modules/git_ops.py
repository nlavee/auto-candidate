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

    def setup_worktree(self, repo_path: str, branch_name: str, worktree_path: str) -> str:
        """
        Creates a new worktree for the given branch at worktree_path.
        Returns the absolute path to the worktree.
        """
        try:
            repo = Repo(repo_path)
            # Ensure worktree_path is absolute
            worktree_abs = os.path.abspath(worktree_path)

            # If path exists, clean it up properly
            if os.path.exists(worktree_abs):
                console.print(f"[yellow]Worktree path exists, cleaning up...[/yellow]")
                try:
                    # Try to remove using git worktree remove first
                    repo.git.worktree('remove', '-f', worktree_abs)
                except GitCommandError:
                    # If that fails, manually remove and prune
                    shutil.rmtree(worktree_abs, ignore_errors=True)
                    repo.git.worktree('prune')

            console.print(f"[cyan]Creating worktree for {branch_name} at {worktree_abs}...[/cyan]")

            # Use git command directly for worktree
            # -b creates the branch if it doesn't exist
            # If branch exists, we might need logic to just checkout,
            # but -B forces creation/reset which is good for a clean start.
            repo.git.worktree('add', '-f', '-B', branch_name, worktree_abs)

            console.print(f"[green]✔ Worktree ready at {worktree_abs}[/green]")
            return worktree_abs
        except GitCommandError as e:
            console.print(f"[red]Failed to create worktree: {e}[/red]")
            raise

    def cleanup_worktree(self, repo_path: str, worktree_path: str) -> None:
        """
        Properly removes a worktree using git worktree remove.
        This ensures the branch commits are preserved in the main repo.
        """
        try:
            repo = Repo(repo_path)
            worktree_abs = os.path.abspath(worktree_path)

            if os.path.exists(worktree_abs):
                console.print(f"[dim]Cleaning up worktree at {worktree_abs}...[/dim]")
                # Use git worktree remove instead of rmtree to properly clean up
                repo.git.worktree('remove', '-f', worktree_abs)
                console.print(f"[green]✔ Worktree cleaned up[/green]")
            else:
                # If directory doesn't exist, prune stale metadata
                repo.git.worktree('prune')
        except GitCommandError as e:
            console.print(f"[yellow]Warning: Failed to cleanup worktree: {e}[/yellow]")
            # Fallback to manual cleanup
            if os.path.exists(worktree_abs):
                shutil.rmtree(worktree_abs, ignore_errors=True)
            try:
                repo.git.worktree('prune')
            except:
                pass

    def merge_feature_branch(self, repo_path: str, target_branch: str, source_branch: str, resolver=None, plan_context: str = "") -> bool:
        """
        Merges source_branch into target_branch.
        Returns True if successful.
        If resolver is provided, attempts to resolve conflicts using LLM.
        """
        try:
            repo = Repo(repo_path)
            
            # Checkout target
            repo.git.checkout(target_branch)
            
            console.print(f"[cyan]Merging {source_branch} into {target_branch}...[/cyan]")
            try:
                repo.git.merge(source_branch)
                console.print(f"[green]✔ Merged {source_branch}[/green]")
                return True
            except GitCommandError:
                if not resolver:
                    raise # Rethrow if no resolver
                
                console.print(f"[yellow]Conflict detected! Attempting AI Resolution...[/yellow]")
                
                # Identify conflicted files
                # Using git diff to get simple list of filenames
                conflicted_files = repo.git.diff('--name-only', '--diff-filter=U').splitlines()
                
                if not conflicted_files:
                     # Maybe it was another error?
                     raise
                
                for file_path in conflicted_files:
                    full_path = os.path.join(repo_path, file_path)
                    try:
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Ask LLM to resolve
                        resolved_content = resolver.resolve_conflict({
                            "file_path": file_path,
                            "conflict_content": content
                        }, plan_context=plan_context)
                        
                        if resolved_content:
                            with open(full_path, 'w', encoding='utf-8') as f:
                                f.write(resolved_content)
                            repo.git.add(file_path)
                            console.print(f"[green]✔ Resolved {file_path}[/green]")
                        else:
                            console.print(f"[red]Failed to resolve {file_path} (Empty response)[/red]")
                            repo.git.merge('--abort')
                            return False
                    except Exception as e:
                        console.print(f"[red]Error resolving {file_path}: {e}[/red]")
                        repo.git.merge('--abort')
                        return False
                
                # Final commit
                repo.git.commit('-m', f"Merge {source_branch} (AI Resolved)")
                console.print(f"[green]✔ Merge committed.[/green]")
                return True
                
        except GitCommandError as e:
            console.print(f"[red]Merge failed for {source_branch}: {e}[/red]")
            try:
                repo.git.merge('--abort')
            except:
                pass
            return False
