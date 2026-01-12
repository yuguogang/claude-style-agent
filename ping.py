import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"

url = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent?key={API_KEY}"

payload = {
    "contents": [
        {
            "role": "user",
            "parts": [{"text": "Say hello in one sentence."}]
        }
    ]
}

r = requests.post(url, json=payload, timeout=60)
print(r.status_code)
print(r.text)
