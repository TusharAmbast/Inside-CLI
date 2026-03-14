import platform
import ollama

# Configuration
MODEL_NAME = "Qwen2.5-1.5B-Instruct:latest"
CURRENT_OS = platform.system()  # 'Windows', 'Darwin' (Mac), or 'Linux'

# Initialize Client
try:
    client = ollama.Client(host="http://localhost:11434")
except:
    print("Error: Could not connect to Ollama. Make sure it is running!")


def get_command_from_text(user_query):
    """
    Converts natural language to a shell command.
    On Windows: targets CMD (cmd.exe) — NOT PowerShell.
    subprocess.run(shell=True) uses cmd.exe on Windows.
    """
    if CURRENT_OS == "Windows":
        shell_name = "Windows CMD (cmd.exe)"
        examples = (
            "User: show current directory\n"
            "Command: cd\n\n"
            "User: list all files\n"
            "Command: dir\n\n"
            "User: show hidden files\n"
            "Command: dir /a\n\n"
            "User: create a folder named test\n"
            "Command: mkdir test\n\n"
            "User: delete file log.txt\n"
            "Command: del log.txt\n\n"
            "User: show running processes\n"
            "Command: tasklist\n\n"
            "User: clear the screen\n"
            "Command: cls\n\n"
        )
    else:
        shell_name = "Bash"
        examples = (
            "User: show current directory\n"
            "Command: pwd\n\n"
            "User: list all files\n"
            "Command: ls -la\n\n"
            "User: show running processes\n"
            "Command: ps aux\n\n"
            "User: clear the screen\n"
            "Command: clear\n\n"
        )

    try:
        response = client.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a {shell_name} command generator.\n"
                        "Rules:\n"
                        "- Output ONLY a single raw command. Nothing else.\n"
                        "- No backticks, no markdown, no explanations, no comments.\n"
                        "- No pipelines unless absolutely necessary.\n"
                        "- Use the simplest possible command that does the job.\n"
                        f"- Commands must work in {shell_name} only.\n\n"
                        "Examples:\n"
                        f"{examples}"
                        f"Now respond with ONLY the command for the user's request."
                    )
                },
                {
                    "role": "user",
                    "content": user_query
                }
            ],
            options={"temperature": 0.1}
        )
        cmd = response['message']['content'].strip()
        # Strip markdown/backticks if model still adds them
        cmd = cmd.replace("```", "").replace("`", "").strip()
        # Take only the first line — ignore any trailing explanation
        cmd = cmd.splitlines()[0].strip()
        # Strip "Command: " prefix if model echoes the format
        if cmd.lower().startswith("command:"):
            cmd = cmd[len("command:"):].strip()
        return cmd
    except Exception as e:
        return f"Error: {e}"


def explain_process_by_pid(pid, process_name):
    """
    Explains what a process does using chat format.
    """
    try:
        response = client.chat(
            model=MODEL_NAME,
            messages=[
                {
                    'role': 'system',
                    'content': 'You are a helpful computer expert who explains processes clearly and briefly.'
                },
                {
                    'role': 'user',
                    'content': f"Explain what the process '{process_name}' (PID: {pid}) does in 2-3 simple sentences."
                }
            ],
            options={"temperature": 0.6}
        )
        return response['message']['content'].strip()
    except Exception as e:
        return f"Could not generate explanation: {e}"