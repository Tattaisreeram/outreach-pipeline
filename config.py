"""Load and validate environment config. Raises immediately if any key is missing."""
import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Missing required env var: {key}")
    return val


def _optional(key: str) -> str:
    return os.getenv(key, "")


OCEAN_API_TOKEN: str = ""
HUNTER_API_KEY: str = ""
PROSPEO_API_KEY: str = ""
BREVO_API_KEY: str = ""
BREVO_SENDER_EMAIL: str = ""
BREVO_SENDER_NAME: str = ""
DEMO_RECIPIENT: str = ""
ANTHROPIC_API_KEY: str = ""


def load() -> None:
    global OCEAN_API_TOKEN, HUNTER_API_KEY, PROSPEO_API_KEY
    global BREVO_API_KEY, BREVO_SENDER_EMAIL, BREVO_SENDER_NAME
    global DEMO_RECIPIENT, ANTHROPIC_API_KEY

    OCEAN_API_TOKEN = _require("OCEAN_API_TOKEN")
    HUNTER_API_KEY = _require("HUNTER_API_KEY")
    PROSPEO_API_KEY = _optional("PROSPEO_API_KEY")
    BREVO_API_KEY = _require("BREVO_API_KEY")
    BREVO_SENDER_EMAIL = _require("BREVO_SENDER_EMAIL")
    BREVO_SENDER_NAME = _require("BREVO_SENDER_NAME")
    DEMO_RECIPIENT = _require("DEMO_RECIPIENT")
    ANTHROPIC_API_KEY = _optional("ANTHROPIC_API_KEY")
