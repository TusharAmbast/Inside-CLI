import platform
import ollama

# Configuration
MODEL_NAME = "Qwen2.5-1.5B-Instruct:latest"  # Check your exact model name in `ollama list`
CURRENT_OS = platform.system()  # Returns 'Windows', 'Darwin' (Mac), or 'Linux'

# Initialize Client
try:
    client = ollama.Client(host="http://localhost:11434")
except:
    print("Error: Could not connect to Ollama. Make sure it is running!")

def get_command_from_text(user_query):
    """
    STRICT MODE: Converts natural language to a shell command.
    """
    # 1. Detect OS to guide the model
    shell_type = "PowerShell" if CURRENT_OS == "Windows" else "Bash/Zsh"
    
    # 2. Construct the Prompt
    # We tell the model explicitly which OS we are on.
    system_instruction = (
        f"You are a command line assistant for {CURRENT_OS} using {shell_type}. "
        "Output ONLY the executable command. No markdown, no explanation."
    )
    
    prompt = f"System: {system_instruction}\nInstruct: {user_query}\nOutput:"

    # 3. Call Ollama (Low Temp = Precise)
    try:
        response = client.generate(
            model=MODEL_NAME,
            prompt=prompt,
            options={
                "temperature": 0.1, 
                "stop": ["Output:", "Instruct:", "\n\n"]
            }
        )
        # Clean up any markdown code blocks if the model adds them
        cmd = response['response'].strip()
        if cmd.startswith("`"): cmd = cmd.replace("`", "")
        return cmd
    except Exception as e:
        return f"Error: {e}"

def explain_process_by_pid(pid, process_name):
    """
    CREATIVE MODE: Explains what a process does using chat format.
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