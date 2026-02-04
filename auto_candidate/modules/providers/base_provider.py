"""
Base abstract class for LLM providers.
Defines the interface that all providers (Gemini, Claude, etc.) must implement.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    All concrete providers (Gemini, Claude, etc.) must implement these methods.
    """

    def __init__(self, api_key: str, model_name: str):
        """
        Initialize the provider.

        Args:
            api_key: API key for the LLM provider
            model_name: Model name to use (provider-specific format)
        """
        self.api_key = api_key
        self.model_name = model_name

    @abstractmethod
    def _call_cli(self, prompt: str, system_instruction: str = "") -> str:
        """
        Core CLI invocation method - provider specific.

        Args:
            prompt: User message/prompt
            system_instruction: System instruction to guide model behavior

        Returns:
            Response text from the LLM
        """
        pass

    @staticmethod
    @abstractmethod
    def list_available_models(api_key: str) -> List[str]:
        """
        Lists all available models for this provider.

        Args:
            api_key: API key for the provider

        Returns:
            List of model names
        """
        pass

    @abstractmethod
    def create_task_breakdown(self, challenge_prompt: str, codebase_context: str) -> Dict[str, Any]:
        """
        Generates a master plan broken down into independent tasks.

        Args:
            challenge_prompt: The coding challenge description
            codebase_context: String representation of the codebase structure

        Returns:
            JSON object with 'plan_overview' and 'tasks' array
        """
        pass

    @abstractmethod
    def execute_task(self, task: Dict[str, Any], codebase_context: str,
                    plan_overview: str = "", task_spec: str = "") -> str:
        """
        Generates code for a specific task.

        Args:
            task: Task dictionary with id, title, description, etc.
            codebase_context: String representation of the codebase
            plan_overview: Overall plan context
            task_spec: Detailed task specification

        Returns:
            Raw LLM response containing file blocks with <<<FILE:>>> syntax
        """
        pass

    @abstractmethod
    def fix_code(self, error_log: str, original_task: str, codebase_context: str) -> str:
        """
        Generates fixed code based on error logs.

        Args:
            error_log: Error message from test/lint failures
            original_task: The original task description
            codebase_context: String representation of the codebase

        Returns:
            Raw LLM response containing file blocks with <<<FILE:>>> syntax
        """
        pass

    @abstractmethod
    def verify_solution(self, original_task: str, codebase_context: str, test_output: str) -> str:
        """
        Verifies if the solution meets the original requirements.

        Args:
            original_task: The original challenge/task description
            codebase_context: Current state of the codebase
            test_output: Output from test execution

        Returns:
            Markdown analysis with compliance check and verdict (PASS/FAIL)
        """
        pass

    @abstractmethod
    def create_master_plan_doc(self, plan_json: Dict[str, Any], codebase_context: str) -> str:
        """
        Generates a detailed master plan markdown document.

        Args:
            plan_json: The task breakdown JSON
            codebase_context: String representation of the codebase

        Returns:
            Markdown content for MASTER_PLAN.md
        """
        pass

    @abstractmethod
    def create_task_spec_doc(self, task: Dict[str, Any], master_plan: str, codebase_context: str) -> str:
        """
        Generates a detailed specification markdown for a single task.

        Args:
            task: Task dictionary
            master_plan: Master plan markdown content
            codebase_context: String representation of the codebase

        Returns:
            Markdown content for PLAN_<task_id>.md
        """
        pass

    @abstractmethod
    def review_and_refine_plan(self, plan_json: Dict[str, Any], master_plan: str, sub_plans: Dict[str, str]) -> str:
        """
        Reviews the plan consistency and suggests improvements.

        Args:
            plan_json: The task breakdown JSON
            master_plan: Master plan markdown content
            sub_plans: Dictionary mapping task_id to task spec content

        Returns:
            'OK' if plan is solid, or corrected JSON string if changes needed
        """
        pass

    @abstractmethod
    def resolve_conflict(self, conflict_info: Dict[str, Any], plan_context: str = "") -> str:
        """
        Resolves a merge conflict based on context.

        Args:
            conflict_info: Dictionary with 'file_path' and 'conflict_content'
            plan_context: Project plan context for reference

        Returns:
            Resolved file content (raw, not wrapped in <<<FILE>>> blocks)
        """
        pass

    @abstractmethod
    def generate_plans(self, challenge_prompt: str, codebase_context: str, num_versions: int = 2) -> List[str]:
        """
        Generates distinct architectural plans based on the challenge.

        Args:
            challenge_prompt: The coding challenge description
            codebase_context: String representation of the codebase
            num_versions: Number of plan versions to generate

        Returns:
            List of plan strings
        """
        pass

    @abstractmethod
    def generate_code(self, plan: str, codebase_context: str) -> str:
        """
        Generates the actual code based on the approved plan.

        Args:
            plan: The implementation plan
            codebase_context: String representation of the codebase

        Returns:
            Raw LLM response containing file blocks with <<<FILE:>>> syntax
        """
        pass
