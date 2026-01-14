import os
import time
import json
import random
import requests
from requests.exceptions import HTTPError, RequestException
from dotenv import load_dotenv

from state_store import init_db, load_state, save_state, clear_state
from tools import run_tool

# --- Configuration ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent?key={API_KEY}"

PHASE_ORDER = ["plan", "act", "reflect"]
MAX_RETRIES = 6
BASE_SLEEP = 1.0
MAX_SLEEP = 30.0
MIN_REQUEST_INTERVAL = 1.2  # Seconds between requests to avoid 429

# --- Helper Functions ---

def generate_content(prompt: str) -> str:
    """
    Calls the Gemini API with exponential backoff for rate limits.
    """
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(API_URL, json=payload, timeout=60)

            # Handle Rate Limiting (429) and Server Errors (5xx)
            if response.status_code == 429 or (500 <= response.status_code < 600):
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        sleep_time = float(retry_after)
                    except ValueError:
                        sleep_time = BASE_SLEEP
                else:
                    # Exponential backoff + Jitter
                    sleep_time = min(MAX_SLEEP, BASE_SLEEP * (2 ** (attempt - 1)))
                    sleep_time = sleep_time * (0.7 + random.random() * 0.6)

                print(f"[WARN] HTTP {response.status_code} (attempt {attempt}/{MAX_RETRIES}). Sleeping {sleep_time:.1f}s...")
                time.sleep(sleep_time)
                continue

            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]

        except HTTPError:
            # Client errors (4xx except 429) should raise immediately
            raise
        except RequestException as e:
            # Network errors: retry
            sleep_time = min(MAX_SLEEP, BASE_SLEEP * (2 ** (attempt - 1)))
            print(f"[WARN] Network error (attempt {attempt}/{MAX_RETRIES}): {e}. Sleeping {sleep_time:.1f}s...")
            time.sleep(sleep_time)

    raise RuntimeError("LLM request failed after max retries.")

def parse_response(text: str) -> dict:
    """
    Parses JSON from LLM output, handling potential Markdown fencing.
    """
    clean_text = text.strip()

    # Remove Markdown code blocks only if they exist
    if clean_text.startswith("```"):
        # Split into lines to remove first and last line (the fences)
        lines = clean_text.splitlines()
        # Remove header fence (e.g., ```json)
        if lines: 
            lines = lines[1:]
        # Remove footer fence (```)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        clean_text = "\n".join(lines).strip()
    
    # Attempt direct extraction
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass

    # Fallback: Extract from first '{' to last '}'
    start_idx = clean_text.find("{")
    end_idx = clean_text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return json.loads(clean_text[start_idx:end_idx+1])

    raise ValueError("No valid JSON found in model output")

def get_next_phase(current_phase: str) -> str:
    try:
        idx = PHASE_ORDER.index(current_phase)
        return PHASE_ORDER[(idx + 1) % len(PHASE_ORDER)]
    except ValueError:
        return PHASE_ORDER[0]

def load_system_prompt() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt_path = os.path.join(base_dir, "prompts", "system.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

def initialize_state() -> dict:
    init_db()
    state = load_state()
    
    if state:
        print("🔁 Current State Found:")
        print(json.dumps(state, indent=2, ensure_ascii=False))
        choice = input("Resume previous task? (Y/n): ").strip().lower()
        if choice == "n":
            clear_state()
            state = None
    
    if not state:
        task = input("Enter your task: ")
        state = {
            "goal": task,
            "constraints": ["Practical", "Step-by-step"],
            "progress": [],
            "current_phase": "plan",
            "next_step": "",
            "observation": None # Explicitly None for clarity
        }
        save_state(state)
        
    return state

# --- Main Logic ---

def main():
    system_prompt = load_system_prompt()
    state = initialize_state()
    
    last_request_time = 0.0

    while True:
        # Rate limiting logic
        time_since_last = time.time() - last_request_time
        if time_since_last < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - time_since_last)
            
        # Construct Prompt
        full_prompt = f"{system_prompt}\n\nSTATE:\n{json.dumps(state, ensure_ascii=False, indent=2)}"
        
        # Call LLM
        raw_response = generate_content(full_prompt)
        last_request_time = time.time()
        
        print("\n🤖 LLM RESPONSE:\n", raw_response)
        
        try:
            parsed_response = parse_response(raw_response)
        except ValueError as e:
            print(f"❌ JSON Parsing Failed: {e}")
            continue

        # Handle Tool Calls
        tool_call = parsed_response.get("tool")
        if tool_call:
            handle_tool_call(state, tool_call)
            input("\nPress Enter to continue...\n")
            continue

        # Handle Normal Agent Step
        handle_agent_step(state, parsed_response)
        
        # Check Completion
        if parsed_response.get("decision") == "done":
            print("\n✅ Task completed.")
            clear_state()
            break

        input("\nPress Enter to continue...\n")


def handle_tool_call(state: dict, tool_call: dict):
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})
    
    print(f"\n�  Executing Tool: {tool_name} {tool_args}")
    
    try:
        result = run_tool(tool_call)
        state["observation"] = {
            "tool": tool_name,
            "args": tool_args,
            "result": result
        }
        print("\n✅ Tool Output:", json.dumps(result, ensure_ascii=False, indent=2))
        
    except Exception as e:
        state["observation"] = {
            "tool": tool_name,
            "error": str(e)
        }
        print(f"\n❌ Tool Error: {e}")

    save_state(state)


def handle_agent_step(state: dict, response: dict):
    # Update state fields from LLM response
    llm_state = response.get("state", {})
    keys_to_update = ["goal", "constraints", "progress", "next_step", "observation"]
    
    for key in keys_to_update:
        if key in llm_state:
            state[key] = llm_state[key]

    # Display Output
    output_message = response.get("output", "")
    if output_message:
        print("\n📝 Agent Output:\n", output_message)

    # Progression Logic
    # We ignore the LLM's 'current_phase' and enforce our own rotation
    current_phase = state.get("current_phase", "plan")
    state["current_phase"] = get_next_phase(current_phase)
    
    save_state(state)


if __name__ == "__main__":
    main()
