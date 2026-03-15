"""Prompt template service for RAG pipelines.

Builds system prompts with context injection and citation instructions.
"""

from __future__ import annotations

from app.domain.entities.chat import ChatMessage, MessageRole

_RAG_SYSTEM_PROMPT = """You are a helpful AI assistant. Answer questions based ONLY on the provided context.

Rules:
1. Use ONLY the information from the [CONTEXT] section below
2. If the context does not contain enough information, say "I don't have enough information to answer that"
3. Cite sources using [1], [2], etc. corresponding to the context blocks
4. Be concise and accurate
5. Do not make up information not present in the context

[CONTEXT]
{context}
[END CONTEXT]"""

_DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant. Be concise and accurate in your responses."""


class PromptService:
    """Builds prompts for RAG chat interactions.

    Handles system prompt construction with context injection
    and citation-formatted context blocks.
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
            query: The user's question.
            context: Pre-formatted context string with numbered blocks.
            history: Optional previous chat messages for continuity.

        Returns:
            Ordered list of ChatMessage for the LLM.
        """
        messages: list[ChatMessage] = []

        # System prompt with injected context
        system_content = _RAG_SYSTEM_PROMPT.format(context=context)
        messages.append(
            ChatMessage(role=MessageRole.SYSTEM, content=system_content)
        )

        # Append chat history for conversation continuity
        if history:
            messages.extend(history)

        # Current user query
        messages.append(
            ChatMessage(role=MessageRole.USER, content=query)
        )

        return messages
