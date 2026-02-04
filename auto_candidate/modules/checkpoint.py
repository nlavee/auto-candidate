"""
Checkpoint management for AutoCandidate workflow.
Allows saving and resuming from intermediate states.
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path


class CheckpointManager:
    """Manages checkpoint creation, loading, and validation for workflow resumption."""

    def __init__(self, workspace_path: str):
        """
        Initialize checkpoint manager.

        Args:
            workspace_path: Path to the workspace directory
        """
        self.workspace_path = workspace_path
        self.checkpoint_file = os.path.join(workspace_path, ".autocandidate_checkpoint.json")

    def save_checkpoint(self, phase: int, state: dict) -> None:
        """
        Save checkpoint to disk.

        Args:
            phase: Current phase number (1-4)
            state: State dictionary to merge into checkpoint
        """
        # Load existing checkpoint or create new one
        if self.checkpoint_exists():
            checkpoint_data = self.load_checkpoint()
        else:
            checkpoint_data = {
                "version": "1.0",
                "workspace": self.workspace_path,
            }

        # Update checkpoint with new state
        checkpoint_data["checkpoint_time"] = datetime.utcnow().isoformat() + "Z"
        checkpoint_data["current_phase"] = phase

        # Update phases_completed list
        phases_completed = set(checkpoint_data.get("phases_completed", []))
        phases_completed.add(phase)
        checkpoint_data["phases_completed"] = sorted(list(phases_completed))

        # Merge state into checkpoint
        checkpoint_data.update(state)

        # Write to disk
        os.makedirs(self.workspace_path, exist_ok=True)
        with open(self.checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint from disk.

        Returns:
            Checkpoint data dictionary, or None if file doesn't exist or is invalid
        """
        if not self.checkpoint_exists():
            return None

        try:
            with open(self.checkpoint_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def checkpoint_exists(self) -> bool:
        """
        Check if checkpoint file exists.

        Returns:
            True if checkpoint file exists
        """
        return os.path.exists(self.checkpoint_file)

    def clear_checkpoint(self) -> None:
        """Delete checkpoint file."""
        if self.checkpoint_exists():
            os.remove(self.checkpoint_file)

    def validate_checkpoint(
        self, prompt_hash: str, workspace: str, repo_path: str
    ) -> bool:
        """
        Validate checkpoint is compatible with current run.

        Args:
            prompt_hash: SHA256 hash of current prompt file
            workspace: Current workspace path
            repo_path: Current repository path

        Returns:
            True if checkpoint is valid and compatible
        """
        checkpoint_data = self.load_checkpoint()
        if not checkpoint_data:
            return False

        # Check workspace matches
        if checkpoint_data.get("workspace") != workspace:
            return False

        # Check repo path matches
        if checkpoint_data.get("repo_path") != repo_path:
            return False

        # Check prompt hash matches (if present)
        saved_hash = checkpoint_data.get("prompt_hash")
        if saved_hash and saved_hash != prompt_hash:
            return False

        return True

    def get_current_phase(self) -> int:
        """
        Get the current phase from checkpoint.

        Returns:
            Current phase number (1-4), or 0 if no checkpoint
        """
        checkpoint_data = self.load_checkpoint()
        if not checkpoint_data:
            return 0

        return checkpoint_data.get("current_phase", 0)

    def get_phases_completed(self) -> List[int]:
        """
        Get list of completed phases.

        Returns:
            List of completed phase numbers
        """
        checkpoint_data = self.load_checkpoint()
        if not checkpoint_data:
            return []

        return checkpoint_data.get("phases_completed", [])


def calculate_prompt_hash(prompt_path: str) -> str:
    """
    Calculate SHA256 hash of prompt file for validation.

    Args:
        prompt_path: Path to prompt file

    Returns:
        SHA256 hash string with 'sha256:' prefix
    """
    if not os.path.exists(prompt_path):
        return ""

    sha256_hash = hashlib.sha256()
    with open(prompt_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return f"sha256:{sha256_hash.hexdigest()}"
