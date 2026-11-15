from custom_types.summary import ChatMessage

from ai.query import query_summary

import asyncio


class SummaryService:
    DEFAULT_MESSAGES = 50
    MAX_MESSAGES = 200

    # Transcript limits
    MAX_TRANSCRIPT_CHARS = 24_000
    MAX_MESSAGE_CHARS = 1_000

    def clamp_count(self, count: int) -> int:
        return max(1, min(count, self.MAX_MESSAGES))

    def _format_line(self, message: ChatMessage) -> str:
        # Collapse newlines / runs of whitespace so each message is one line
        content = " ".join(message.content.split())
        if len(content) > self.MAX_MESSAGE_CHARS:
            content = content[: self.MAX_MESSAGE_CHARS].rstrip() + "…"

        timestamp = message.timestamp.strftime("%Y-%m-%d %H:%M")
        return f"[{timestamp}] {message.author}: {content}"

    def build_transcript(self, messages: list[ChatMessage]) -> str:
        """Build a transcript from messages in chronological order (oldest first).

        Drops the oldest lines first if the transcript exceeds the character budget.
        """
        kept: list[str] = []
        total = 0
        for message in reversed(messages):
            line = self._format_line(message)
            cost = len(line) + 1  # +1 for the joining newline
            if kept and total + cost > self.MAX_TRANSCRIPT_CHARS:
                break
            kept.append(line)
            total += cost

        kept.reverse()
        return "\n".join(kept)

    async def summarise(self, messages: list[ChatMessage]) -> str:
        if not messages:
            raise ValueError("There are no messages to summarise.")

        transcript = self.build_transcript(messages)
        return await asyncio.to_thread(query_summary, transcript)
