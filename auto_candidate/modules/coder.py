import os
import re
from typing import List
from rich.console import Console
from rich.panel import Panel

console = Console()

class FilePatcher:
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)

    def apply_patches(self, llm_response: str) -> List[str]:
        """
        Parses the LLM response for <<<FILE: path>>> blocks and writes them to disk.
        Returns a list of modified file paths.
        """
        # Regex to find blocks.
        # structure: <<<FILE: path>>> 
        pattern = r"<<<FILE: (.*?)>>>\s*(.*?)<<<END_FILE>>>"
        matches = re.findall(pattern, llm_response, re.DOTALL)
        
        modified_files = []

        if not matches:
            console.print("[yellow]No file blocks found in LLM response. The model might have just chatted instead of coding.[/yellow]")
            console.print(f"[dim]Raw Response Preview:\n{llm_response[:500]}...[/dim]")
            return []

        for rel_path, content in matches:
            rel_path = rel_path.strip()
            # Safety check: Prevent directory traversal
            full_path = os.path.abspath(os.path.join(self.root_dir, rel_path))
            if not full_path.startswith(self.root_dir):
                console.print(f"[red]Skipping unsafe path: {rel_path}[/red]")
                continue

            # Create directory if needed
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            try:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content.strip())
                console.print(f"[green]✔ Wrote {rel_path}[/green]")
                modified_files.append(rel_path)
            except Exception as e:
                console.print(f"[red]Failed to write {rel_path}: {e}[/red]")

        return modified_files