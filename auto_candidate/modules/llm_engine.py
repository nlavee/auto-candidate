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

    def create_task_breakdown(self, challenge_prompt: str, codebase_context: str) -> dict:
        """
        Generates a master plan broken down into independent tasks.
        Returns a JSON object with 'plan_overview' and 'tasks'.
        """
        console.print(f"[cyan]Formulating task-based plan via Gemini ({self.model_name})...[/cyan]")
        
        system_instruction = (
            "You are a Technical Project Manager and Architect.\n"
            "Goal: Break down the coding challenge into a series of small, executable, and modular tasks.\n"
            "Output Format: PURE JSON ONLY. No markdown fences.\n"
            "Structure:\n"
            "{\n"
            "  \"plan_overview\": \"...\",\n"
            "  \"tasks\": [\n"
            "    {\n"
            "      \"id\": \"task_01\",\n"
            "      \"title\": \"...\",\n"
            "      \"description\": \"Detailed instructions for the developer...\",\n"
            "      \"input_context\": [\"path/to/relevant/file.py\"], \n"
            "      \"target_files\": [\"path/to/new_or_modified_file.py\"], \n"
            "      \"dependencies\": []\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "Requirements:\n"
            "1. Tasks should be as independent as possible to allow parallel coding.\n"
            "2. 'target_files' are the files this task will create or modify.\n"
            "3. 'input_context' are files this task needs to read to understand the codebase.\n"
        )

        user_message = (
            f"CHALLENGE PROMPT:\n{challenge_prompt}\n\n"
            f"CURRENT CODEBASE CONTEXT:\n{codebase_context}\n\n"
            f"TASK:\n"
            f"Create a modular implementation plan. Return ONLY the JSON structure."
        )

        try:
            response_text = self._call_cli(user_message, system_instruction)
            
            # Clean up potential markdown fences if the model ignores instructions
            cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
            
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            console.print(f"[red]Failed to parse plan JSON: {e}[/red]")
            console.print(f"[dim]Raw: {response_text[:500]}...[/dim]")
            return {}
        except Exception as e:
            console.print(f"[bold red]Gemini Execution Error:[/bold red] {e}")
            return {}

    def execute_task(self, task: dict, codebase_context: str, plan_overview: str = "", task_spec: str = "") -> str:
        """
        Generates code for a specific task.
        Returns the raw LLM response containing file blocks.
        """
        console.print(f"[cyan]Executing Task: {task.get('title')} ({self.model_name})...[/cyan]")

        system_instruction = (
            "You are a Senior Python Developer implementing a specific task within a larger project plan.\n"
            "You MUST output code using the following strict format for every file:\n\n"
            "<<<FILE: path/to/file.py>>>\n"
            "... full file content ...\n"
            "<<<END_FILE>>>\n\n"
            "Rules:\n"
            "1. Rewrite the ENTIRE file content. Do not use placeholders.\n"
            "2. Do not wrap the blocks in Markdown code fences.\n"
            "3. Ensure the path is relative to the project root.\n"
            "4. Only modify/create the files listed in 'Target Files' unless absolutely necessary.\n"
            "5. Ensure your implementation aligns with the overall plan and respects dependencies."
        )

        user_message = (
            f"OVERALL PLAN:\n{plan_overview}\n\n"
            f"DETAILED TASK SPEC:\n{task_spec}\n\n"
            f"CONTEXT:\n{codebase_context}\n\n"
            f"TASK DESCRIPTION:\n{task.get('description')}\n\n"
            f"DEPENDENCIES:\n{json.dumps(task.get('dependencies', []))}\n\n"
            f"TARGET FILES:\n{json.dumps(task.get('target_files'))}\n\n"
            f"INSTRUCTION:\n"
            f"Write the code to implement this task. Output ALL necessary files using the <<<FILE: path>>> syntax."
        )

        try:
            return self._call_cli(user_message, system_instruction)
        except Exception as e:
            console.print(f"[bold red]Gemini Execution Error during coding:[/bold red] {e}")
            return ""

    def fix_code(self, error_log: str, original_task: str, codebase_context: str) -> str:
        """
        Generates fixed code based on error logs.
        Returns the raw LLM response containing file blocks.
        """
        console.print(f"[cyan]Attempting to fix code errors ({self.model_name})...[/cyan]")

        system_instruction = (
            "You are a Senior Python Developer fixing a bug.\n"
            "You MUST output code using the following strict format for every file:\n\n"
            "<<<FILE: path/to/file.py>>>\n"
            "... full file content ...\n"
            "<<<END_FILE>>>\n\n"
            "Rules:\n"
            "1. Rewrite the ENTIRE file content. Do not use placeholders.\n"
            "2. Do not wrap the blocks in Markdown code fences.\n"
            "3. Ensure the path is relative to the project root.\n"
            "4. Analyze the error log carefully and fix the specific issue."
        )

        user_message = (
            f"CONTEXT:\n{codebase_context}\n\n"
            f"ORIGINAL TASK:\n{original_task}\n\n"
            f"ERROR LOG:\n{error_log}\n\n"
            f"INSTRUCTION:\n"
            f"Fix the code to resolve the errors. Output ALL necessary files using the <<<FILE: path>>> syntax."
        )

        try:
            return self._call_cli(user_message, system_instruction)
        except Exception as e:
            console.print(f"[bold red]Gemini Execution Error during debugging:[/bold red] {e}")
            return ""

    def verify_solution(self, original_task: str, codebase_context: str, test_output: str) -> str:
        """
        Verifies if the solution meets the original requirements.
        Returns a markdown analysis.
        """
        console.print(f"[cyan]Verifying solution against requirements...[/cyan]")
        
        system_instruction = (
            "You are a QA Lead. Goal: Verify if the implemented solution meets the original requirements.\n"
            "Output: A Markdown report.\n"
            "Include:\n"
            "- Compliance Checklist\n"
            "- Identified Gaps (if any)\n"
            "- Final Verdict (PASS/FAIL)"
        )
        
        user_message = (
            f"ORIGINAL REQUIREMENTS:\n{original_task}\n\n"
            f"CURRENT CODEBASE CONTEXT:\n{codebase_context}\n\n"
            f"TEST EXECUTION OUTPUT:\n{test_output}\n\n"
            f"INSTRUCTION:\n"
            f"Assess the solution validity."
        )
        
        try:
            return self._call_cli(user_message, system_instruction)
        except Exception as e:
            console.print(f"[red]Verification failed: {e}[/red]")
            return "Verification Failed"

    def create_master_plan_doc(self, plan_json: dict, codebase_context: str) -> str:
        """Generates a detailed master plan markdown document."""
        console.print(f"[cyan]Generating Master Plan Document ({self.model_name})...[/cyan]")
        
        system_instruction = (
            "You are a Technical Lead. Goal: Write a comprehensive MASTER IMPLEMENTATION PLAN (Markdown).\n"
            "Include: \n"
            "- Architecture Overview\n"
            "- Dependencies & Configuration\n"
            "- Build Steps\n"
            "- Versioning Strategy\n"
            "- Testing Protocols\n"
            "- Deployment & Rollback Procedures\n"
        )
        
        user_message = (
            f"TASKS JSON:\n{json.dumps(plan_json, indent=2)}\n\n"
            f"CONTEXT:\n{codebase_context}\n\n"
            f"INSTRUCTION:\n"
            f"Write the MASTER_PLAN.md content."
        )
        
        try:
            return self._call_cli(user_message, system_instruction)
        except Exception as e:
            console.print(f"[red]Failed to generate master plan doc: {e}[/red]")
            return "# Master Plan Generation Failed"

    def create_task_spec_doc(self, task: dict, master_plan: str, codebase_context: str) -> str:
        """Generates a detailed specification markdown for a single task."""
        console.print(f"[cyan]Generating Spec for Task: {task.get('title')}...[/cyan]")
        
        system_instruction = (
            "You are a Technical Lead. Goal: Write a detailed TASK SPECIFICATION (Markdown).\n"
            "Audience: The developer who will implement this task in isolation.\n"
            "Include:\n"
            "- Objectives\n"
            "- Input/Output Contracts\n"
            "- Detailed Implementation Steps\n"
            "- Verification Steps\n"
        )
        
        user_message = (
            f"MASTER PLAN:\n{master_plan}\n\n"
            f"TASK:\n{json.dumps(task, indent=2)}\n\n"
            f"CONTEXT:\n{codebase_context}\n\n"
            f"INSTRUCTION:\n"
            f"Write the TASK_PLAN.md content."
        )
        
        try:
            return self._call_cli(user_message, system_instruction)
        except Exception as e:
            console.print(f"[red]Failed to generate task spec: {e}[/red]")
            return "# Task Spec Generation Failed"

    def review_and_refine_plan(self, plan_json: dict, master_plan: str, sub_plans: dict) -> str:
        """
        Reviews the plan consistency.
        Returns 'OK' if good, or a NEW JSON string if changes are needed.
        """
        console.print(f"[cyan]Reviewing Plans for Consistency...[/cyan]")
        
        system_instruction = (
            "You are a Chief Architect. Goal: Validated the proposed implementation plan.\n"
            "Check for:\n"
            "- Gaps in logic\n"
            "- Missing dependencies\n"
            "- Contradictions between master plan and tasks\n"
            "Output:\n"
            "If the plan is solid, output exactly: OK\n"
            "If the plan needs work, output ONLY the corrected JSON for the task breakdown."
        )
        
        # Prepare summary of sub-plans
        sub_plan_summary = "\n".join([f"Task {t_id}: {content[:200]}..." for t_id, content in sub_plans.items()])
        
        user_message = (
            f"CURRENT JSON PLAN:\n{json.dumps(plan_json, indent=2)}\n\n"
            f"MASTER PLAN DOC:\n{master_plan}\n\n"
            f"SUB-PLAN SUMMARIES:\n{sub_plan_summary}\n\n"
            f"INSTRUCTION:\n"
            f"Review. Output 'OK' or the corrected JSON."
        )
        
        try:
            return self._call_cli(user_message, system_instruction)
        except Exception as e:
            console.print(f"[red]Plan review failed: {e}[/red]")
            return "OK" # Fail open to avoid blocking

    def resolve_conflict(self, conflict_info: dict, plan_context: str = "") -> str:
        """
        Resolves a merge conflict based on context.
        Returns the resolved file content string (not the <<<FILE>>> block).
        """
        console.print(f"[cyan]Resolving conflict in {conflict_info.get('file_path')} ({self.model_name})...[/cyan]")

        system_instruction = (
            "You are a Senior Python Developer resolving a git merge conflict.\n"
            "Goal: Return the CORRECTLY resolved content for the file.\n"
            "Rules:\n"
            "1. Output ONLY the raw content of the resolved file. No markdown fences.\n"
            "2. Preserve the intent of both changes if possible, or prioritize the FEATURE branch (HEAD) if it adds new functionality.\n"
            "3. Ensure the code is syntactically correct and aligns with the overall project plan.\n"
        )
        
        context_msg = f"PROJECT PLAN CONTEXT:\n{plan_context}\n\n" if plan_context else ""

        user_message = (
            f"{context_msg}"
            f"FILE PATH: {conflict_info.get('file_path')}\n\n"
            f"CONFLICT CONTEXT:\n{conflict_info.get('conflict_content')}\n\n"
            f"INSTRUCTION:\n"
            f"Resolve the conflict. Return the clean file content."
        )

        try:
            return self._call_cli(user_message, system_instruction)
        except Exception as e:
            console.print(f"[bold red]Gemini Execution Error during conflict resolution:[/bold red] {e}")
            return ""

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
