import os
from dotenv import load_dotenv
from pathlib import Path


# .env
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# AI backend: "anthropic" or "openrouter". AI_MODEL optionally overrides the default model.
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic").lower()
AI_MODEL = os.getenv("AI_MODEL")
ANTHROPIC_TOKEN = os.getenv("ANTHROPIC_TOKEN")
OPENROUTER_TOKEN = os.getenv("OPENROUTER_TOKEN")

assert DISCORD_TOKEN
if AI_PROVIDER == "anthropic":
    assert ANTHROPIC_TOKEN, "ANTHROPIC_TOKEN is required when AI_PROVIDER=anthropic"
elif AI_PROVIDER == "openrouter":
    assert OPENROUTER_TOKEN, "OPENROUTER_TOKEN is required when AI_PROVIDER=openrouter"

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
WORDS_PATH = BASE_DIR / "resources" / "words.json"
