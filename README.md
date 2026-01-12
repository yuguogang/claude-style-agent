# Claude-Style Agent (Python)

A minimal "Plan-Act-Reflect" agent implementation in Python, using the Gemini API.

## Structure

```text
.
├── .env.example            # Environment variables template
├── requirements.txt        # Python dependencies
├── src/
│   ├── agent.py            # Main agent loop and logic
│   └── tools/              # Tool implementations (Web, Shell, Files)
├── prompts/
│   └── system.md           # System prompt for the agent
├── tests/                  # Tests
└── scripts/
    └── run_demo.sh         # Helper script to run the agent
```

## Setup

1.  **Environment**:
    ```bash
    cp .env.example .env
    # Edit .env and add your GEMINI_API_KEY
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the agent using the helper script:

```bash
./scripts/run_demo.sh
```

Or directly via python:

```bash
python -m src.agent
```
