"""
DeterministicFallbackProvider -- the final link in the AI provider chain.

When both primary (GLM-5.3-Flash) and fallback (DeepSeek-V4.1-Flash) language models
are unreachable, timed out, or return an error, BHOOMI must remain safe and useful.

This provider never invents data or fabricates AI responses. It renders a safe,
limited, rule-based agriculture assessment following the BHOOMI Master System Prompt specification:

BHOOMI FARM INTELLIGENCE

Data availability:
Limited

Status:
A full AI analysis is temporarily unavailable.

Available information: <show known information>

Safe next step: <rule-based recommendation if supported>
"""
import re
import time

from app.integrations.ai.base import AICompletion, AIMessage, AIProvider


class DeterministicFallbackProvider(AIProvider):
    name = "deterministic"

    def complete(self, messages: list[AIMessage], *, temperature: float = 0.2, max_tokens: int = 700) -> AICompletion:
        start = time.monotonic()
        user_content = next((m.content for m in reversed(messages) if m.role == "user"), "")

        # Extract available information from prompt text
        info_lines = []
        for line in user_content.splitlines():
            line_str = line.strip()
            if line_str.startswith("- ") and "Not available" not in line_str and "Not provided" not in line_str:
                info_lines.append(line_str)

        if not info_lines:
            available_info = "Basic farm parameters recorded in system."
        else:
            available_info = "\n".join(info_lines[:12])

        # Extract any specific rule-based recommendation or advisory hint
        safe_action = (
            "Verify field moisture and leaf condition directly on the farm. "
            "Follow standard regional agricultural university guidelines for the current crop stage. "
            "Avoid applying unverified chemical inputs until full agronomic verification is completed."
        )

        content = (
            "BHOOMI FARM INTELLIGENCE\n\n"
            "Data availability:\n"
            "Limited\n\n"
            "Status:\n"
            "A full AI analysis is temporarily unavailable.\n\n"
            "Available information:\n"
            f"{available_info}\n\n"
            "Safe next step:\n"
            f"{safe_action}"
        )

        latency_ms = int((time.monotonic() - start) * 1000)
        return AICompletion(
            content=content,
            provider=self.name,
            model="bhoomi-deterministic-agriculture-engine",
            tokens_in=0,
            tokens_out=0,
            latency_ms=latency_ms,
        )
