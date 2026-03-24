import os

from dotenv import load_dotenv


load_dotenv()


MONGODB_URL = os.getenv("MONGODB_URL", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "dpms_chat")
MONGODB_CONVERSATIONS_COLLECTION = os.getenv("MONGODB_CONVERSATIONS_COLLECTION", "conversations")


def validate_conversation_settings() -> None:
    if not MONGODB_URL:
        raise ValueError("MONGODB_URL is required")
    print(f"Using MongoDB URL: {MONGODB_URL}")


validate_conversation_settings()
