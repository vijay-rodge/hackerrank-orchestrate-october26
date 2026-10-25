"""
Provider-independent AI Adapter for Ghost Data Auditor.
Supports deterministic offline fallback and Google Gemini SDK integration.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("ghost_auditor.ai")


class SemanticEvidenceInsight(BaseModel):
    """Pydantic validated structured insight from narrative/unstructured evidence."""
    intent_authorized: bool = Field(description="Whether the request text authorizes deletion")
    resource_ids: List[str] = Field(default_factory=list, description="Extracted resource identifiers")
    user_identifiers: List[str] = Field(default_factory=list, description="Extracted emails or user IDs")
    reasoning: str = Field(default="", description="Grounded factual reasoning")


class AIAdapter:
    """
    Configurable AI adapter supporting Gemini and deterministic offline fallback.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Initialized Google GenAI client with model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI SDK: {e}. Falling back to offline engine.")
                self.client = None

    def analyze_unstructured_evidence(self, text: str) -> SemanticEvidenceInsight:
        """Analyze unstructured evidence text and return validated schema."""
        if self.client:
            try:
                prompt = (
                    "Analyze the following evidence text for data governance auditing. "
                    "Extract user identifiers (emails, user IDs), resource IDs (account_, search_, etc.), "
                    "and whether the subject explicitly requested deletion.\n\n"
                    f"Evidence Text:\n{text}"
                )
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": SemanticEvidenceInsight,
                    }
                )
                if response and response.parsed:
                    return response.parsed
                elif response and response.text:
                    return SemanticEvidenceInsight.model_validate_json(response.text)
            except Exception as e:
                logger.warning(f"AI call failed: {e}. Using deterministic fallback.")

        # Deterministic offline fallback
        import re
        res_matches = re.findall(r'\b(account_\d+|search_\d+|support_\d+|analytics_\d+|data_flow_\d+|backup_\d+|audit_record_\d+|tombstone_\d+|export_\d+)\b', text)
        email_matches = [e.lower() for e in re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)]
        uid_matches = re.findall(r'\buser_\d+\b', text)
        
        t_low = text.lower()
        negative_signals = ["not asking for deletion", "leave the account", "without removing", "marketing lists only"]
        authorized = not any(sig in t_low for sig in negative_signals) and any(w in t_low for w in ["delete", "remove", "erase", "close", "purge"])

        return SemanticEvidenceInsight(
            intent_authorized=authorized,
            resource_ids=list(set(res_matches)),
            user_identifiers=list(set(email_matches + uid_matches)),
            reasoning="Extracted via deterministic pattern analysis."
        )

