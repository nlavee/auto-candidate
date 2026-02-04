"""
LLM Engine module - now a compatibility layer.
The actual implementation has been moved to providers/gemini_provider.py.
This file maintains backward compatibility by re-exporting GeminiProvider as GeminiPlanner.
"""
from .providers.gemini_provider import GeminiProvider as GeminiPlanner

# Re-export for backward compatibility
__all__ = ['GeminiPlanner']
