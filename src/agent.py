import os
import json
import requests
import time
import random
from requests.exceptions import HTTPError, RequestException

from dotenv import load_dotenv

from state_store import init_db, load_state, save_state, clear_state
from tools import run_tool

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent?key={API_KEY}"

PHASE_ORDER = ["plan", "act", "reflect"]

def call_llm(prompt: str, max_retries: int = 6) -> str:
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }

    # 基础退避参数
    base_sleep = 1.0  # seconds
    max_sleep = 30.0  # cap

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(API_URL, json=payload, timeout=60)

            # 对 429/5xx 做重试，其余 raise
            if r.status_code == 429 or (500 <= r.status_code < 600):
                retry_after = r.headers.get("Retry-After")
                if retry_after:
                    try:
                        sleep_s = float(retry_after)
                    except ValueError:
                        sleep_s = base_sleep
                else:
                    # 指数退避 + 抖动
                    sleep_s = min(max_sleep, base_sleep * (2 ** (attempt - 1)))
                    sleep_s = sleep_s * (0.7 + random.random() * 0.6)  # jitter 0.7~1.3

                print(f"[WARN] HTTP {r.status_code} (attempt {attempt}/{max_retries}). Sleeping {sleep_s:.1f}s then retry...")
                time.sleep(sleep_s)
                continue

            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

        except HTTPError as e:
            # 非 429/5xx 的 HTTP 错误通常是参数/权限问题，不要重试
            raise
        except RequestException as e:
            # 网络抖动等：也退避重试
            sleep_s = min(max_sleep, base_sleep * (2 ** (attempt - 1)))
            sleep_s = sleep_s * (0.7 + random.random() * 0.6)
            print(f"[WARN] Network error (attempt {attempt}/{max_retries}): {e}. Sleeping {sleep_s:.1f}s...")
            time.sleep(sleep_s)

    raise RuntimeError("LLM request failed after retries (rate limit or network).")


def extract_json(text: str) -> dict:
    """
    Robustly parse JSON from model output, tolerating markdown fences or extra text.
    """
    t = text.strip()

    # Remove ```json ... ``` fences if present
    if t.startswith("```"):
        # remove first fence line
        lines = t.splitlines()
        if lines:
            lines = lines[1:]
        # remove last fence if present
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()

    # Direct parse
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    # Fallback: take substring from first { to last }
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(t[start:end+1])

    raise ValueError("No valid JSON found in model output")

def next_phase(current: str) -> str:
    try:
        i = PHASE_ORDER.index(current)
    except ValueError:
        return "plan"
    return PHASE_ORDER[(i + 1) % len(PHASE_ORDER)]

def main():
    # project root path resolve
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt_path = os.path.join(base_dir, "prompts", "system.md")

    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    init_db()

    state = load_state()
    if state:
        ans = input("🔁 Resume previous task? (Y/n): ").strip().lower()
        if ans == "n":
            clear_state()
            state = None

    if not state:
        goal = input("Enter your task: ")
        state = {
            "goal": goal,
            "constraints": ["Practical", "Step-by-step"],
            "progress": [],
            "current_phase": "plan",
            "next_step": ""
        }
        save_state(state)
    last_call_ts = 0.0
    min_interval_s = 1.2
    while True:
        full_prompt = system_prompt + "\n\nSTATE:\n" + json.dumps(state, ensure_ascii=False, indent=2)

        now = time.time()
        wait = min_interval_s - (now - last_call_ts)
        if wait > 0:
            time.sleep(wait)
        last_call_ts = time.time()
        response_text = call_llm(full_prompt)
        print("\nLLM RAW OUTPUT:\n", response_text)

        if response_text.strip().startswith("{") or response_text.strip().startswith("```"):
             # Optional: Try to pretty print if it looks like JSON
             pass # We print raw output above already
        
        response = extract_json(response_text)

        # ---- Tool calling: only when model asks for it
        tool_req = response.get("tool")
        if tool_req:
            try:
                tool_result = run_tool(tool_req)
                state["observation"] = {
                    "tool": tool_req.get("name"),
                    "args": tool_req.get("args", {}),
                    "result": tool_result,
                }
                # 关键：工具执行后不强制前进 phase，让模型下一轮在 REFLECT/PLAN 消化 observation
                save_state(state)
                print("\n🔧 TOOL RESULT:\n", json.dumps(state["observation"], ensure_ascii=False, indent=2))
            except Exception as e:
                state["observation"] = {
                    "tool": tool_req.get("name"),
                    "error": str(e),
                }
                save_state(state)
                print("\n❌ TOOL ERROR:\n", json.dumps(state["observation"], ensure_ascii=False, indent=2))

            input("\nPress Enter to continue...\n")
            continue

        # ---- Normal response path
        llm_state = response.get("state", {})
        decision = response.get("decision", "continue")
        output = response.get("output", "")

        print("\nOUTPUT:\n", output)

        # 合并 state（保留必要字段），并收回 phase 控制权
        # 你也可以改成更严格的 schema 校验
        for k in ["goal", "constraints", "progress", "next_step", "observation", "current_phase"]:
            if k in llm_state:
                state[k] = llm_state[k]

        # phase 由程序推进（防止模型劫持）
        state["current_phase"] = next_phase(state.get("current_phase", "plan"))

        save_state(state)

        if decision == "done":
            print("\n✅ Task completed.")
            clear_state()
            break

        input("\nPress Enter to continue...\n")

if __name__ == "__main__":
    main()
