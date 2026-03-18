from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ── Gemini 1.5 Models ─────────────────────────
response = client.models.generate_content(
    model="models/gemini-flash-latest",       # or "gemini-1.5-pro"
    contents="What is vendor management?"
)
print(response.text)