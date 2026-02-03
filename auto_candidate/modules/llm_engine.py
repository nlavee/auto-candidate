import os
import json
import subprocess
import time
import google.generativeai as genai
from rich.console import Console

console = Console()

class GeminiPlanner:
    def __init__(self, api_key: str, model_name: str):
        # Configure genai just in case list_available_models is called or needed later
        genai.configure(api_key=api_key)
        self.model_name = model_name

    def _call_cli(self, prompt: str, system_instruction: str = "") -> str:
        """Calls the 'gemini' CLI command and returns the response string."""
        full_prompt = f"{system_instruction}\n\n{prompt}"
        
        def run_cmd(model_arg):
            # Always ensure the prefix is gone for the CLI
            clean_arg = model_arg.replace("models/", "")
            cmd = [
                "gemini", 
                # Prompt passed via stdin
                "--output-format", "json",
                "--model", clean_arg
            ]
            return subprocess.run(cmd, input=full_prompt, capture_output=True, text=True, check=True)

        # Potential candidates to try
        candidates = []
        original = self.model_name
        candidates.append(original)
        
        # Add stripped version if not already there
        if "models/" in original:
            candidates.append(original.replace("models/", ""))

        # Deduplicate preserving order
        unique_candidates = []
        for c in candidates:
            if c not in unique_candidates:
                unique_candidates.append(c)

        last_error = None
        for model_try in unique_candidates:
            try:
                if model_try != original:
                    console.print(f"[dim]Retrying with model: {model_try}...[/dim]")
                
                result = run_cmd(model_try)
                
                # Robust JSON parsing: find the first '{' and last '}'
                stdout_str = result.stdout.strip()
                json_start = stdout_str.find('{')
                json_end = stdout_str.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_str = stdout_str[json_start:json_end]
                    data = json.loads(json_str)
                else:
                    # Fallback or error
                    data = json.loads(stdout_str)
                
                return data.get("response", "")
                
            except subprocess.CalledProcessError as e:
                last_error = e
                # Continue if model not found (404) or Bad Request (400)
                if "ModelNotFoundError" in e.stderr or "404" in e.stderr or "400" in e.stderr:
                    continue
                else:
                    # Log other errors but maybe try next model anyway
                    console.print(f"[yellow]CLI Warning with {model_try}: {e.stderr.strip()[:200]}...[/yellow]")
                    if "429" in e.stderr: # Quota
                         console.print("[yellow]Quota exceeded. Sleeping 2s...[/yellow]")
                         time.sleep(2)
                    continue
            except json.JSONDecodeError as e:
                console.print(f"[red]Failed to parse CLI output as JSON: {e}[/red]")
                # console.print(f"[dim]Output: {result.stdout[:200]}...[/dim]")
                # Try next model?
                continue

        console.print(f"[bold red]All model attempts failed.[/bold red]")
        if last_error:
            # Re-raise the last error if all failed
            raise last_error
        return ""

    @staticmethod
    def list_available_models(api_key: str) -> list[str]:
        """Lists all models that support content generation using the Python SDK."""
        genai.configure(api_key=api_key)
        models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    models.append(m.name)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not fetch dynamic model list ({e}). Using defaults.[/yellow]")
            return [
                "models/gemini-2.0-flash",
            ]
        return sorted(models, reverse=True)

    def generate_plans(self, challenge_prompt: str, codebase_context: str, num_versions: int = 2) -> list[str]:
        """
        Generates distinct architectural plans based on the challenge and codebase.
        Returns a list of plan strings.
        """
        console.print(f"[cyan]Contacting Gemini CLI ({self.model_name}) to formulate plans...[/cyan]")
        
        system_instruction = (
            "You are a Senior Python Software Architect helping a candidate with a take-home coding challenge.\n"
            "Your goal is to provide specific, actionable implementation plans.\n"
            "GUIDELINES:\n"
            "1. **Do not refactor** existing code unless absolutely necessary (e.g., it's broken). Extend it.\n"
            "2. Assume a Docker environment is available.\n"
            "3. Focus on Python best practices (typing, tests).\n"
        )

        user_message = (
            f"CHALLENGE PROMPT:\n{challenge_prompt}\n\n"
            f"CURRENT CODEBASE CONTEXT:\n{codebase_context}\n\n"
            f"TASK:\n"
            f"Create {num_versions} distinct implementation plans to solve this challenge.\n"
            f"Version 1 should be the 'Pragmatic approach': Simplest code to pass requirements, leveraging existing patterns.\n"
            f"Version 2 should be the 'Engineered approach': Focus on extensibility, Dependency Injection, and robust error handling.\n\n"
            f"For EACH version, provide:\n"
            f"1. A high-level summary of the architectural choice.\n"
            f"2. A step-by-step implementation guide (e.g., '1. Create model X', '2. Update view Y').\n"
            f"3. A list of exact file paths to create or modify.\n\n"
            f"Separate the two plans clearly with a delimiter like '=== PLAN SEPARATOR ==='."
        )

        try:
            full_text = self._call_cli(user_message, system_instruction)
            
            if "=== PLAN SEPARATOR ===" in full_text:
                plans = full_text.split("=== PLAN SEPARATOR ===")
            else:
                plans = [full_text]
            
            return [p.strip() for p in plans[:num_versions]]

        except Exception as e:
            console.print(f"[bold red]Gemini Execution Error:[/bold red] {e}")
            return []

    def generate_code(self, plan: str, codebase_context: str) -> str:
        """
        Generates the actual code based on the approved plan.
        Returns the raw LLM response containing file blocks.
        """
        console.print(f"[cyan]Generating code via Gemini CLI ({self.model_name})...[/cyan]")

        system_instruction = (
            "You are a Senior Python Developer implementing a technical plan.\n"
            "You MUST output code using the following strict format for every file:\n\n"
            "<<<FILE: path/to/file.py>>>\n"
            "... full file content ...\n"
            "<<<END_FILE>>>\n\n"
            "Rules:\n"
            "1. Rewrite the ENTIRE file content. Do not use placeholders like '# ... rest of code'.\n"
            "2. Do not wrap the blocks in Markdown code fences (no ```python).\n"
            "3. Ensure the path is relative to the project root.\n"
        )

        user_message = (
            f"CONTEXT:\n{codebase_context}\n\n"
            f"PLAN TO IMPLEMENT:\n{plan}\n\n"
            f"TASK:\n"
            f"Write the code to implement this plan. Output ALL necessary files using the <<<FILE: path>>> syntax."
        )

        try:
            return self._call_cli(user_message, system_instruction)
        except Exception as e:
            console.print(f"[bold red]Gemini Execution Error during coding:[/bold red] {e}")
            return ""
