"""Root pytest config — load .env so eval tests can reach API keys."""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()
