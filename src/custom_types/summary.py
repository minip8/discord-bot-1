from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ChatMessage:
    author: str  # display name
    content: str  # plain message text
    timestamp: datetime
