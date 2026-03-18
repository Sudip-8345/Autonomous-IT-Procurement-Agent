import os
from dotenv import load_dotenv

load_dotenv()

AMAZON_BASE_URL = "https://www.amazon.in"
FLIPKART_BASE_URL = "https://www.flipkart.com"

DEFAULT_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT_MS", "45000"))
DEFAULT_MAX_RESULTS_PER_PLATFORM = int(os.getenv("MAX_RESULTS_PER_PLATFORM", "6"))
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "1.4"))

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

USER_AGENT = os.getenv(
    "PROC_AGENT_USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "   # Gecko -> Firefox, AppleWebKit -> Chrome/Safari
        "Chrome/122.0.0.0 Safari/537.36"
    ),
)

