import os

from dotenv import load_dotenv


load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def validate_agent_settings() -> None:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required")


validate_agent_settings()
