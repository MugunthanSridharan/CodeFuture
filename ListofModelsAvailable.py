import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Available Models:")
print("-" * 60)
for model in client.models.list():
    print(model.name)