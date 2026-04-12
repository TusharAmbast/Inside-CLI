import platform
import ollama

# Configuration
MODEL_NAME = "Qwen2.5-1.5B-Instruct:latest"
CURRENT_OS = platform.system()  # 'Windows', 'Darwin' (Mac), or 'Linux'

# Initialize Client
client = None
try:
    client = ollama.Client(host="http://localhost:11434")
except Exception as e:
    print(f"Critique-CLI Warning: Could not connect to Ollama. {e}")


# ─── Lookup Tables ────────────────────────────────────────────────────────────
# Simple everyday commands that the model was never trained on.
# Keyed by normalized phrase → command string.
# The model is only called if no match is found here.

WINDOWS_COMMANDS = {
    # directory navigation
    "current directory"             : "cd",
    "show current directory"        : "cd",
    "show me the current directory" : "cd",
    "what is the current directory" : "cd",
    "where am i"                    : "cd",
    "print working directory"       : "cd",
    "pwd"                           : "cd",
    "go up"                         : "cd ..",
    "go back"                       : "cd ..",
    "go up one directory"           : "cd ..",
    "go home"                       : "cd %USERPROFILE%",
    "go to home"                    : "cd %USERPROFILE%",
    "go to documents"               : "cd %USERPROFILE%\\Documents",
    "go to desktop"                 : "cd %USERPROFILE%\\Desktop",
    "go to downloads"               : "cd %USERPROFILE%\\Downloads",
    # listing files
    "list files"                    : "dir",
    "list all files"                : "dir /a",
    "show files"                    : "dir",
    "show all files"                : "dir /a",
    "show hidden files"             : "dir /a",
    "list hidden files"             : "dir /a",
    "ls"                            : "dir",
    "ls -a"                         : "dir /a",
    "ls -la"                        : "dir /a",
    # screen
    "clear"                         : "cls",
    "clear screen"                  : "cls",
    "clear the screen"              : "cls",
    "clear terminal"                : "cls",
    # processes
    "show processes"                : "tasklist",
    "list processes"                : "tasklist",
    "show running processes"        : "tasklist",
    "list running processes"        : "tasklist",
    "what processes are running"    : "tasklist",
    "running processes"             : "tasklist",
    # network
    "show ip"                       : "ipconfig",
    "show ip address"               : "ipconfig",
    "what is my ip"                 : "ipconfig",
    "ip address"                    : "ipconfig",
    "network info"                  : "ipconfig",
    "show network"                  : "ipconfig",
    # system info
    "computer name"                 : "hostname",
    "show computer name"            : "hostname",
    "hostname"                      : "hostname",
    "current user"                  : "whoami",
    "show current user"             : "whoami",
    "who am i"                      : "whoami",
    "logged in user"                : "whoami",
    "system info"                   : "systeminfo",
    "show system info"              : "systeminfo",
    "environment variables"         : "set",
    "show environment variables"    : "set",
    "show env"                      : "set",
    # date/time
    "show date"                     : "date /t",
    "show time"                     : "time /t",
    "date"                          : "date /t",
    "time"                          : "time /t",
    "show date and time"            : "date /t && time /t",
    # disk
    "disk space"                    : "wmic logicaldisk get size,freespace,caption",
    "show disk space"               : "wmic logicaldisk get size,freespace,caption",
    "check disk space"              : "wmic logicaldisk get size,freespace,caption",
    "free space"                    : "wmic logicaldisk get size,freespace,caption",
}

MAC_COMMANDS = {
    # directory navigation
    "current directory"             : "pwd",
    "show current directory"        : "pwd",
    "show me the current directory" : "pwd",
    "what is the current directory" : "pwd",
    "where am i"                    : "pwd",
    "print working directory"       : "pwd",
    "pwd"                           : "pwd",
    "go up"                         : "cd ..",
    "go back"                       : "cd ..",
    "go up one directory"           : "cd ..",
    "go home"                       : "cd ~",
    "go to home"                    : "cd ~",
    "go to documents"               : "cd ~/Documents",
    "go to desktop"                 : "cd ~/Desktop",
    "go to downloads"               : "cd ~/Downloads",
    # listing files
    "list files"                    : "ls",
    "list all files"                : "ls -la",
    "show files"                    : "ls",
    "show all files"                : "ls -la",
    "show hidden files"             : "ls -a",
    "list hidden files"             : "ls -a",
    "ls"                            : "ls",
    # screen
    "clear"                         : "clear",
    "clear screen"                  : "clear",
    "clear the screen"              : "clear",
    "clear terminal"                : "clear",
    # processes
    "show processes"                : "ps aux",
    "list processes"                : "ps aux",
    "show running processes"        : "ps aux",
    "list running processes"        : "ps aux",
    "what processes are running"    : "ps aux",
    "running processes"             : "ps aux",
    # network
    "show ip"                       : "ifconfig",
    "show ip address"               : "ifconfig",
    "what is my ip"                 : "ifconfig",
    "ip address"                    : "ifconfig",
    "network info"                  : "ifconfig",
    "show network"                  : "ifconfig",
    # system info
    "computer name"                 : "hostname",
    "show computer name"            : "hostname",
    "hostname"                      : "hostname",
    "current user"                  : "whoami",
    "show current user"             : "whoami",
    "who am i"                      : "whoami",
    "logged in user"                : "whoami",
    "system info"                   : "uname -a",
    "show system info"              : "uname -a",
    "environment variables"         : "env",
    "show environment variables"    : "env",
    "show env"                      : "env",
    # date/time
    "show date"                     : "date",
    "show time"                     : "date",
    "date"                          : "date",
    "time"                          : "date",
    "show date and time"            : "date",
    # disk
    "disk space"                    : "df -h",
    "show disk space"               : "df -h",
    "check disk space"              : "df -h",
    "free space"                    : "df -h",
}


def _lookup(user_query: str) -> str | None:
    """
    Normalize the query and check against the lookup table.
    Returns the command if found, None if not.
    Two strategies:
      1. Exact match after normalization
      2. Partial match — query contains a known phrase or vice versa
    """
    table = WINDOWS_COMMANDS if CURRENT_OS == "Windows" else MAC_COMMANDS
    q     = user_query.lower().strip()

    # Strategy 1: exact match
    if q in table:
        return table[q]

    # Strategy 2: partial match
    for phrase, cmd in table.items():
        if phrase in q or q in phrase:
            return cmd

    return None


# ─── Main functions ───────────────────────────────────────────────────────────

def get_command_from_text(user_query):
    """
    1. Check lookup table first — instant and reliable for everyday commands.
    2. Fall back to model only for complex queries it was trained on
       (git operations, find pipelines, bulk renames, etc.)
    """
    # Fast path — lookup table
    quick = _lookup(user_query)
    if quick:
        return quick

    # Slow path — model (for complex queries)
    try:
        response = client.generate(
            model=MODEL_NAME,
            prompt=f"Instruct: {user_query}\nOutput:",
            options={
                "temperature": 0.1,
                "stop": ["Instruct:", "Output:", "<|endoftext|>"]
            }
        )
        cmd = response['response'].strip()
        cmd = cmd.replace("```", "").replace("`", "").strip()
        cmd = cmd.splitlines()[0].strip()
        return cmd
    except Exception as e:
        return f"Error: {e}"


def classify_process_importance(pid: int, process_name: str) -> str:
    """
    Asks the LLM whether a process is safe to kill or critical to the system.
    Used as Layer 3 fallback in anomaly.py when Layers 1 & 2 are inconclusive.

    Returns:
        'safe'     — process can be safely terminated
        'critical' — process is important, should not be killed
    """
    try:
        response = client.generate(
            model=MODEL_NAME,
            prompt=(
                f"Instruct: Is the process '{process_name}' (PID: {pid}) "
                f"safe to terminate on a running system, or is it a critical "
                f"system/OS process that should not be killed? "
                f"Reply with exactly one word: safe or critical.\nOutput:"
            ),
            options={
                "temperature": 0.1,
                "stop": ["Instruct:", "Output:", "<|endoftext|>"]
            }
        )
        result = response['response'].strip().lower().split()[0]
        if result in ('safe', 'critical'):
            return result
        # If the model returns something unexpected, fall back conservatively
        return 'critical'
    except Exception:
        return 'critical'


def explain_process_by_pid(pid, process_name):
    """
    Explains what a process does.
    Uses the exact Instruct/Output format the model was trained on.
    """
    try:
        response = client.generate(
            model=MODEL_NAME,
            prompt=f"Instruct: Explain what the process '{process_name}' (PID: {pid}) does in 2-3 simple sentences.\nOutput:",
            options={
                "temperature": 0.6,
                "stop": ["Instruct:", "Output:", "<|endoftext|>"]
            }
        )
        return response['response'].strip()
    except Exception as e:
        return f"Could not generate explanation: {e}"