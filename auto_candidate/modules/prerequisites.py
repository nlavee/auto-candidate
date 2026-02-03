import os
import sys
import docker
import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv

console = Console()

class PrerequisiteChecker:
    def __init__(self):
        load_dotenv()

    def check_docker(self) -> bool:
        """Checks if Docker is installed and running."""
        try:
            client = docker.from_env()
            client.ping()
            console.print("[green]✔ Docker is running.[/green]")
            return True
        except docker.errors.DockerException:
            console.print(Panel(
                "[bold red]Docker is not available![/bold red]\n\n"
                "The script assumes a Docker environment is available for running tests/builds.\n"
                "Possible fixes:\n"
                "1. Ensure Docker Desktop/Engine is started.\n"
                "2. Check if your user has permission to access the docker socket (e.g., `sudo usermod -aG docker $USER`).\n"
                "3. Install Docker if missing.",
                title="Environment Error"
            ))
            return False
        except Exception as e:
            console.print(f"[red]Error checking Docker: {e}[/red]")
            return False

    def check_api_key(self) -> str:
        """Checks for GEMINI_API_KEY and validates basic connectivity."""
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            console.print(Panel(
                "[bold red]GEMINI_API_KEY not found![/bold red]\n\n"
                "Please set your API key in a .env file or export it as an environment variable.\n"
                "Example: export GEMINI_API_KEY='your-key-here'",
                title="Configuration Error"
            ))
            sys.exit(1)
        
        # Simple validation (configure only)
        try:
            genai.configure(api_key=api_key)
            # We won't make a call yet to save quota/time, just ensuring the lib accepts it.
            console.print("[green]✔ Gemini API Key found.[/green]")
            return api_key
        except Exception as e:
            console.print(f"[red]Error configuring Gemini: {e}[/red]")
            sys.exit(1)
