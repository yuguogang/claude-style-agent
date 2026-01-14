import os
import subprocess
from typing import Dict, Any

# 项目根目录：.../src/.. = project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# shell 安全白名单（你可以按需增减）
SHELL_ALLOWLIST_PREFIX = (
    "ls", "pwd", "whoami",
    "python", "python3",
    "pytest",
    "git",  # 如果你想完全禁 git，可删
    "cat", "sed", "grep", "rg",
)

def _safe_path(path: str) -> str:
    """
    Restrict file operations to within project root.
    """
    abs_path = os.path.abspath(os.path.join(BASE_DIR, path))
    if not abs_path.startswith(BASE_DIR + os.sep):
        raise ValueError("Path escapes project directory")
    return abs_path

def tool_shell(cmd: str) -> Dict[str, Any]:
    """
    Run a shell command with basic allowlist protection.
    """
    cmd = cmd.strip()
    if not cmd:
        raise ValueError("Empty shell cmd")

    # very small allowlist: only allow commands starting with allowed prefixes
    first = cmd.split()[0]
    if first not in SHELL_ALLOWLIST_PREFIX:
        raise ValueError(f"Shell command not allowed: {first}")

    p = subprocess.run(
        cmd,
        shell=True,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=30
    )
    return {
        "returncode": p.returncode,
        "stdout": (p.stdout or "")[-4000:],
        "stderr": (p.stderr or "")[-4000:],
    }

def tool_read_file(path: str) -> Dict[str, Any]:
    abs_path = _safe_path(path)
    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()
    # 防止太长撑爆上下文
    return {"path": path, "content": content[-12000:]}

def tool_write_file(path: str, content: str) -> Dict[str, Any]:
    abs_path = _safe_path(path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"path": path, "bytes_written": len(content.encode("utf-8"))}

def run_tool(tool: Dict[str, Any]) -> Dict[str, Any]:
    name = tool.get("name")
    args = tool.get("args") or {}

    if name == "shell":
        return tool_shell(args["cmd"])
    if name == "read_file":
        return tool_read_file(args["path"])
    if name == "write_file":
        return tool_write_file(args["path"], args["content"])

    raise ValueError(f"Unknown tool: {name}")
