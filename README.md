# Claude-Style Agent (Python)

A minimal "Plan-Act-Reflect" agent implementation in Python, using the Gemini API.

## 🚀 Quick Start

One command to run the demo (after setup):

```bash
./scripts/run_demo.sh
```

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description | Required | example |
| :--- | :--- | :--- | :--- | 
| `GEMINI_API_KEY` | Your Google Gemini API Key | Yes | `AIzaSy...` |
| `HTTP_PROXY` | Proxy URL (if needed) | No | `http://127.0.0.1:7890` |
| `HTTPS_PROXY` | Proxy URL (if needed) | No | `http://127.0.0.1:7890` |

## 🧪 Reproducible Example

**Input**:
```text
Plan a 1-day trip to Tokyo
```

**Expected Output**:
The agent should enter a loop:
1. **PLAN**: Creates a high-level itinerary logic.
2. **ACT**: Generates specific activities (e.g., Shibuya Crossing, Meiji Shrine).
3. **REFLECT**: Checks if the plan is practical.
4. **Final Decision**: `done`

*Sample Log fragment*:
```json
{
  "state": {
    "current_phase": "act",
    "next_step": "Draft morning activities..."
  },
  "output": "Morning: Visit Meiji Shrine...",
  "decision": "continue"
}
```

## 🔧 Troubleshooting

### 1. 400 Bad Request / 403 Forbidden
*   **Cause**: Invalid API Key.
*   **Fix**: Check `.env` file. Ensure no extra spaces or quotes around the key (e.g., `KEY=AIza...` not `KEY="AIza..."` if using some parsers, though `python-dotenv` handles quotes well).

### 2. 404 Not Found
*   **Cause**: Model name incorrect or API endpoint changed.
*   **Fix**: Check `src/agent.py` for `MODEL` variable (currently `gemini-2.5-flash`).

### 3. Connection Error / Timeout
*   **Cause**: Network issues or GFW (for users in restricted regions).
*   **Fix**: Set `HTTP_PROXY` and `HTTPS_PROXY` in your environment or terminal before running.

### 4. JSONDecodeError
*   **Cause**: LLM returned malformed JSON or markdown text that wasn't stripped correctly.
*   **Fix**: The code includes logic to strip ```json blocks, but if it fails, check the "LLM RAW OUTPUT" logs.
