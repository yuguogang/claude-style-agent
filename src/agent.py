import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent?key={API_KEY}"

def call_llm(prompt):
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }
    r = requests.post(
        f"{API_URL}",
        json=payload,
        timeout=60
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def main():
    # Resolve path relative to this script
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt_path = os.path.join(base_dir, "prompts", "system.md")
    
    with open(prompt_path) as f:
        system_prompt = f.read()

    goal = input("Enter your task: ")

    state = {
        "goal": goal,
        "constraints": ["Practical", "Step-by-step"],
        "progress": [],
        "current_phase": "plan",
        "next_step": ""
    }

    while True:
        full_prompt = (
            system_prompt
            + "\n\nSTATE:\n"
            + json.dumps(state, indent=2)
        )

        response_text = call_llm(full_prompt)
        print("\nLLM RAW OUTPUT:\n", response_text)

        # Strip markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.strip("`")
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        response = json.loads(response_text)

        state = response["state"]

        if response["decision"] == "done":
            print("\n✅ Task completed.")
            break

        input("\nPress Enter to continue...\n")

if __name__ == "__main__":
    main()
