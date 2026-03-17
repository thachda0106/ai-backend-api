"""Prompt template service — CRIT-7 Fix (prompt injection safety).

Uses a safe string replacement instead of .format() to prevent
crafted context content from escaping the template.
"""

from __future__ import annotations

from app.domain.entities.chat import ChatMessage, MessageRole

# Safe placeholder that cannot appear in user content
_CONTEXT_PLACEHOLDER = "%%CONTEXT%%"

_RAG_SYSTEM_PROMPT = f"""You are a helpful AI assistant. Answer questions based ONLY on the provided context.

Rules:
1. Use ONLY the information from the [CONTEXT] section below
2. If the context does not contain enough information, say "I don't have enough information to answer that"
3. Cite sources using [1], [2], etc. corresponding to the context blocks
4. Be concise and accurate
5. Do not make up information not present in the context

[CONTEXT]
{_CONTEXT_PLACEHOLDER}
[END CONTEXT]"""

_DEFAULT_SYSTEM_PROMPT = "You are a helpful AI assistant. Be concise and accurate in your responses."


class PromptService:
    """Builds prompts for RAG chat interactions.

    Safe context injection: uses explicit placeholder replacement
    instead of Python .format(), which would allow {braces} in
    document content to corrupt the template structure.
    """

    def build_system_prompt(self) -> str:
        """Return the default system prompt (without context)."""
        return _DEFAULT_SYSTEM_PROMPT

    def build_rag_prompt(
        self,
        query: str,
        context: str,
        history: list[ChatMessage] | None = None,
    ) -> list[ChatMessage]:
        """Build a complete message list for RAG chat.

        Args:
            query:   The user's question.
            context: Pre-formatted context string with numbered blocks.
            history: Optional previous chat messages for continuity.

        Returns:
            Ordered list of ChatMessage for the LLM.
        """
        messages: list[ChatMessage] = []

        # CRIT-7 Fix: safe replacement, not .format(context=context)
        # This prevents { or } in document content from corrupting the template
        system_content = _RAG_SYSTEM_PROMPT.replace(_CONTEXT_PLACEHOLDER, context)

        messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_content))

        # Append conversation history (last N messages for continuity)
        if history:
            messages.extend(history)

        # Current user query
        messages.append(ChatMessage(role=MessageRole.USER, content=query))

        return messages
