import os
from typing import List, Dict
from rich.tree import Tree
from rich.console import Console

console = Console()

class ContextBuilder:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.ignore_patterns = {
            '.git', '__pycache__', 'venv', 'env', 'node_modules', 
            '.idea', '.vscode', '.DS_Store', 'poetry.lock', 'yarn.lock'
        }
        self.ignore_extensions = {
            '.pyc', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', 
            '.zip', '.tar', '.gz', '.db', '.sqlite', '.sqlite3'
        }

    def _should_ignore(self, name: str) -> bool:
        if name in self.ignore_patterns:
            return True
        if any(name.endswith(ext) for ext in self.ignore_extensions):
            return True
        return False

    def get_file_tree(self) -> str:
        """Generates a visual string representation of the file tree."""
        tree_str = []
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if not self._should_ignore(d)]
            level = root.replace(self.repo_path, '').count(os.sep)
            indent = ' ' * 4 * (level)
            tree_str.append(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                if not self._should_ignore(f):
                    tree_str.append(f"{subindent}{f}")
        return "\n".join(tree_str)

    def get_context_string(self) -> str:
        """Reads all relevant files and concatenates them for the LLM."""
        context_parts = []
        
        # Add Tree Structure first
        context_parts.append("=== PROJECT STRUCTURE ===")
        context_parts.append(self.get_file_tree())
        context_parts.append("\n=== FILE CONTENTS ===")

        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if not self._should_ignore(d)]
            
            for file in files:
                if self._should_ignore(file):
                    continue
                    
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.repo_path)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        # Skip very large files
                        if len(content) > 100000: 
                            content = "<TRUNCATED: File too large>"
                        
                        context_parts.append(f"\n--- START FILE: {rel_path} ---")
                        context_parts.append(content)
                        context_parts.append(f"--- END FILE: {rel_path} ---")
                except Exception as e:
                    console.print(f"[yellow]Skipping read of {rel_path}: {e}[/yellow]")

        return "\n".join(context_parts)
