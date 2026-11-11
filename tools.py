"""
Optimized Desktop Operator Tools for Needle 3.
Engineered with few-shot docstrings and explicit parameter schemas
to prevent ungrounded command rejections and domain confusion.
"""

import os
import subprocess
from typing import Any, Dict

try:
    import cactus
    tool_decorator = cactus.tool
except ImportError:
    def tool_decorator(fn):
        return fn


# Common phonetic aliases for small ASR models
APP_ALIASES = {
    "cloud": "chrome",
    "crew": "chrome",
    "crow": "chrome",
    "klon": "chrome",
    "google": "chrome",
    "browser": "chrome",
    "vs code": "code",
    "vscode": "code",
    "calculator": "calc",
    "notes": "notepad",
    "terminal": "powershell"
}


@tool_decorator
def open_application(app_name: str) -> Dict[str, Any]:
    """
    Opens or launches a desktop application, browser, or tool on Windows.
    Use when user says 'open chrome', 'launch notepad', 'open code', 'open calc', 'open explorer'.
    
    Args:
        app_name: The application name or alias (e.g. 'chrome', 'notepad', 'code', 'calc', 'explorer', 'cmd').
    """
    clean_name = app_name.strip().lower().replace(".exe", "")
    target_app = APP_ALIASES.get(clean_name, clean_name)
    
    print(f"\n[TOOL: open_application] -> {target_app} (from '{app_name}')")
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", f"Start-Process {target_app}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if proc.returncode == 0:
            return {"status": "success", "message": f"Launched '{target_app}'"}
        else:
            return {"status": "failed", "message": proc.stderr.strip() or f"Could not launch '{target_app}'"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@tool_decorator
def run_powershell(command: str) -> Dict[str, Any]:
    """
    Executes a PowerShell or CLI command on Windows.
    Use for git actions (e.g. 'git status', 'git log'), file listings (e.g. 'dir'),
    or running any shell script or executable.
    
    Args:
        command: The shell command to run (e.g. 'git status', 'dir', 'Get-Process').
    """
    if not command or not command.strip():
        return {"status": "error", "message": "Command parameter cannot be empty."}

    # Phonetic fix for ASR mishearings
    cmd_clean = command.strip()
    if cmd_clean.lower() in ["good status", "get status", "git"]:
        cmd_clean = "git status"
    elif cmd_clean.lower() in ["open"]:
        # If user said 'open' without target, try launching chrome
        return open_application("chrome")

    print(f"\n[TOOL: run_powershell] -> {cmd_clean}")
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", cmd_clean],
            capture_output=True,
            text=True,
            timeout=30
        )
        output = proc.stdout.strip() if proc.stdout else proc.stderr.strip()
        return {
            "status": "success" if proc.returncode == 0 else "failed",
            "exit_code": proc.returncode,
            "output": output[:2000]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@tool_decorator
def check_installed(tool_name: str) -> Dict[str, Any]:
    """
    Checks if a CLI tool, runtime, or programming language is installed on the system.
    Use when user asks if node, git, python, npm, docker, or any program is installed.
    
    Args:
        tool_name: The name of the executable or program (e.g. 'node', 'git', 'python', 'npm').
    """
    clean_name = tool_name.strip().lower().replace(".exe", "")
    print(f"\n[TOOL: check_installed] -> {clean_name}")
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", f"Get-Command {clean_name} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source"],
            capture_output=True,
            text=True,
            timeout=10
        )
        path = proc.stdout.strip()
        if path:
            return {"installed": True, "tool": clean_name, "path": path}
        else:
            return {"installed": False, "tool": clean_name, "message": f"'{clean_name}' was not found in PATH."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@tool_decorator
def restart_process(target: str) -> Dict[str, Any]:
    """
    Stops and restarts a local script, background server, or gateway.
    
    Args:
        target: The file or process name to cycle (e.g. 'proxy.mjs', 'gateway.js', 'launch_free_agent.ps1').
    """
    if not target or not target.strip():
        return {"status": "error", "message": "Target parameter cannot be empty."}

    print(f"\n[TOOL: restart_process] -> {target}")
    try:
        kill_cmd = (
            f"Get-Process | Where-Object {{ $_.ProcessName -like '*{target}*' -or "
            f"$_.CommandLine -like '*{target}*' }} | Stop-Process -Force -ErrorAction SilentlyContinue"
        )
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", kill_cmd], capture_output=True)

        if target.endswith(".mjs") or target.endswith(".js"):
            subprocess.Popen(["node", target], shell=True)
        elif target.endswith(".ps1"):
            subprocess.Popen(["powershell.exe", "-NoProfile", "-File", target], shell=True)
        elif target.endswith(".py"):
            subprocess.Popen(["python", target], shell=True)

        return {"status": "restarted", "target": target}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@tool_decorator
def read_file_content(path: str, lines: int = 25) -> Dict[str, Any]:
    """
    Reads the content or last N lines of any file, document, markdown file, or log.
    
    Args:
        path: Relative or absolute file path (e.g. 'README.md', 'proxy.log', 'package.json').
        lines: Number of lines to read from the end of the file. Default is 25.
    """
    if not path or not path.strip():
        return {"status": "error", "message": "Path parameter cannot be empty."}

    # Phonetic fix: 'radio.md' -> 'README.md'
    clean_path = path.strip()
    if clean_path.lower() in ["radio.md", "read me.md", "read.md"] and not os.path.exists(clean_path):
        if os.path.exists("README.md"):
            clean_path = "README.md"

    print(f"\n[TOOL: read_file_content] -> {clean_path} ({lines} lines)")
    if not os.path.exists(clean_path):
        return {"status": "error", "message": f"File '{clean_path}' does not exist."}

    try:
        with open(clean_path, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            chunk = "".join(all_lines[-lines:])
            return {"status": "success", "path": clean_path, "content": chunk}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@tool_decorator
def trigger_fallback(reason: str, query: str) -> Dict[str, Any]:
    """
    Fallback tool invoked for general knowledge questions, chit-chat, trivia, philosophy, 
    life questions, or anything unrelated to running local tools, files, or terminal commands.
    
    Args:
        reason: Explanation of why fallback was triggered.
        query: Original user input or question.
    """
    print(f"\n[TOOL: trigger_fallback] -> Reason: {reason} | Query: {query}")
    return {"status": "fallback_invoked", "reason": reason, "query": query, "message": "Query is conversational or out-of-scope for desktop tools."}


OPERATOR_TOOLS = [open_application, run_powershell, check_installed, restart_process, read_file_content, trigger_fallback]
