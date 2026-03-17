from warnings import simplefilter

simplefilter(action='ignore', category=FutureWarning)

import sys
import os
import subprocess
import shlex
try:
    import readline
except ImportError:
    import pyreadline3 as readline  

from io import StringIO
from io import TextIOWrapper
import ai_engine  # Import our new file
from animations import Animations
from inside_cli_ascii import main_animation
anim = main_animation()
# anim = Animations()

def find_in_path(command):
    default_path = "/bin:/usr/bin:/usr/local/bin"
    if os.name == "nt":
        default_path = r"C:\Windows\System32;C:\Windows;C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin"
    paths = os.environ.get("PATH", default_path).split(os.pathsep)
    for path in paths:
        full_path = os.path.join(path, command)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path
        if os.name == "nt":
            full_path_exe = f"{full_path}.exe"
            if os.path.isfile(full_path_exe) and os.access(full_path_exe, os.X_OK):
                return full_path_exe
    return None

# REPLACE IT WITH THIS NEW FUNCTION
def monitor_system(*args):
    """
    Launches the PySide6 system monitor in a new,
    non-blocking process.
    """
    try:
        # Get the path to the current Python executable
        python_executable = sys.executable 
        
        # Get the directory of the currently running main.py script
        script_dir = os.path.dirname(__file__)
        
        # Get the full path to the system_monitor.py script
        monitor_script_path = os.path.join(script_dir, "system_monitor.py")

        # Use Popen to launch it as a new process and NOT wait for it.
        # This is the non-blocking part.
        subprocess.Popen([python_executable, monitor_script_path])
        
        # Return a message to the CLI
        return "System monitor launched in a separate window.\n"
        
    except FileNotFoundError:
        return f"Error: Could not find '{monitor_script_path}'.\n"
    except Exception as e:
        return f"Failed to launch system monitor: {e}\n"

def cd_command(*args):
    if not args:
        target_dir = os.path.expanduser("~")
    else:
        path = args[0]
        target_dir = os.path.expanduser(path)
        target_dir = os.path.abspath(target_dir)

    try:
        os.chdir(target_dir)
    except FileNotFoundError:
        return f"cd: {target_dir}: No such file or directory\n"
    except NotADirectoryError:
        return f"cd: {target_dir}: Not a directory\n"
    except PermissionError:
        return f"cd: {target_dir}: Permission denied\n"


def type_command(*args):
    global path
    for cmd in args:
        if cmd in commands:
            return(f"{cmd} is a shell builtin\n")
        else:
            path = find_in_path(cmd)
            if path:
                return(f"{cmd} is {path}\n")
            else:
                return(f"{cmd}: not found\n")
            
def pwd():
    return os.getcwd() + "\n"

def echo(*args):
    if os.name == "nt":
        reserved_names = ["PRN", "CON", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"]
        for arg in args:
            if arg.upper() in reserved_names:
                return f"echo: {arg} is a reserved device name on Windows\n"
    return " ".join(args) + "\n"

hist = []
append_index = 0
def history(*args):
    global hist
    # history in read mode
    if len(args) > 0 and args[0] == "-r":
        if len(args) < 2:
            print("history -r: missing file operand")
            return
        history_file = args[1]
        try:
            with open(history_file, "r") as f:
                for line in f:
                    cmd = line.strip()
                    if cmd:  # skip empty lines
                        hist.append(cmd)
                        readline.add_history(cmd)
        except FileNotFoundError:
            print(f"history -r: {history_file}: No such file")
        return
    
    # history in write mode
    if len(args) > 0 and args[0] == "-w":
        if len(args) < 2:
            print("history -w: missing file operand")
            return
        history_file = args[1]
        try:
            with open(history_file, "w") as f:
                for i in range(len(hist)):
                    f.write(hist[i] + "\n")

        except FileNotFoundError:
            print(f"history -r: {history_file}: No such file")
        return
    
    # history in append mode
    global append_index
    if len(args) > 0 and args[0] == "-a":
        if len(args) < 2:
            print("history -a: missing file operand")
            return
        history_file = args[1]
        try:
            with open(history_file, "a") as f:
                for cmd in hist[append_index:]:
                    f.write(cmd + "\n")
                append_index = len(hist) 
        except FileNotFoundError:
            print(f"history -a: {history_file}: No such file")
        return

    try:
        n = int(args[0]) if len(args) > 0 else len(hist)
    except ValueError:
        print("history: argument must be an integer")
        return
    for i in range(len(hist)-n, len(hist)):
        print(f"{i + 1} {hist[i]}")
     
def cd_exit(*args):
    global hist
    histfile = os.environ.get("HISTFILE")
    if histfile:
        with open(histfile, "w") as f:
            for cmd in hist:
                f.write(cmd + "\n")
    try:
        exit_code = int(args[0]) if args else 0
    except ValueError:
        exit_code = 0
    os._exit(exit_code)
    
commands = {
    "exit": cd_exit,
    "echo":  echo,
    "type": type_command,
    "pwd": pwd,
    "cd": cd_command,
    "history": history,
    "monitor": monitor_system,
}

# For autocompletion
def get_executables_in_path():
    exes = set()
    for dir in os.environ.get("PATH", "").split(":"):
        if os.path.isdir(dir):
            for item in os.listdir(dir):
                full = os.path.join(dir, item)
                if os.access(full, os.X_OK) and os.path.isfile(full):
                    exes.add(item)
    return sorted(exes)

BUILTINS = ["cd", "pwd", "echo", "exit", "type","history", "monitor"]

global last_text, tab_count, last_matches
last_text = ""
tab_count = 0
last_matches = []

def longest_common_prefix(strings):
    if not strings:
        return ""
    prefix = os.path.commonprefix(strings)
    return prefix

def completer(text, state):
    global last_text, tab_count, last_matches
    all_cmds = BUILTINS + list(get_executables_in_path())
    if text != last_text:
        tab_count = 0
        last_text = text
        last_matches = sorted([cmd for cmd in all_cmds if cmd.startswith(text)])
    matches = last_matches
    if not matches:
        return None
          
    # Prioritize built-ins for ech -> echo
    builtin_matches = [cmd for cmd in matches if cmd in BUILTINS]
    if builtin_matches and state == 0:
        return builtin_matches[0] + ' '
    
    # LCP logic: if multiple matches, complete to LCP (if longer than text)
    if len(matches) > 1 and state == 0:
        lcp = longest_common_prefix(matches)
        if lcp != text:
            return lcp + ""    
    
    if len(matches) == 1 and state == 0:
        return matches[0] + ' '
    if state > 0:
        return None
    tab_count += 1
    if tab_count == 1:
        sys.stdout.write('\a')
        sys.stdout.flush()
        return text  # No completion
    elif tab_count == 2:
        print()  # Newline before match list
        print("  ".join(matches))  # Display matches
        sys.stdout.write(f"$ {text}")  # Redisplay prompt
        sys.stdout.flush()
        return text  # Keep prompt
    return text

readline.set_completer(completer)
readline.parse_and_bind("tab: complete")
readline.parse_and_bind("set editing-mode emacs")
readline.parse_and_bind("set keymap emacs")

def load_history():
    for item in hist:
        readline.add_history(item)

def cat (command, args):
    path = find_in_path(command)
    if path:
        try :
            process = subprocess.run([command] + args, executable=path,capture_output=True, text=True)
            return(process.stdout, process.stderr)
        except Exception as e:
                return(f"Error executing {command}: {e}")
    else:
        return(f"{command}: command not found")

# ---------------------------------------------------------------main----------------------------------------------------

def main():
    # Set default PATH for robust command execution
    if not os.environ.get("PATH"):
        default_path = "/bin:/usr/bin:/usr/local/bin"
        if os.name == "nt":
            default_path = r"C:\Windows\System32;C:\Windows;C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin"
        os.environ["PATH"] = default_path
    
    # Load $HISTFILE if set and exists, before loading other history
    histfile = os.environ.get("HISTFILE")
    if histfile and os.path.exists(histfile):
        with open(histfile, "r") as f:
            for line in f:
                cmd = line.strip()
                if cmd:
                    global hist
                    hist.append(cmd)
                    readline.add_history(cmd)
    load_history()
    
    # anim.banner()
    anim
    # print("Welcome to my CLI Baby!")
    print(" ")
    
    try:
        while True:
            cmd = input("$ ")
            hist.append(cmd)
            
            command_with_args = shlex.split(cmd)
            if not command_with_args:
                continue
            command = command_with_args[0]
            args = command_with_args[1:]

            # Handle Windows built-in commands
            windows_builtins = ["dir", "copy", "del", "move"]
            if os.name == "nt" and (command in windows_builtins or command == "ls"):
                if command == "ls":
                    command = "dir"  # Map ls to dir on Windows
                try:
                    result = subprocess.run([command] + args, shell=True, text=True, capture_output=True)
                    print(result.stdout, end="")
                    if result.stderr:
                        print(result.stderr, end="")
                except Exception as e:
                    print(f"Error executing {command}: {e}")
                continue

            # Handle pipeline commands
            if "|" in command_with_args:
                pipeline = []
                current_cmd = []
                for token in command_with_args:
                    if token == "|":
                        if current_cmd:
                            pipeline.append(current_cmd)
                            current_cmd = []
                    else:
                        current_cmd.append(token)
                if current_cmd:
                    pipeline.append(current_cmd)
                if not pipeline or any(len(cmd) == 0 for cmd in pipeline):
                    print("Invalid pipeline syntax")
                    continue

                processes = []
                for i, cmd_args in enumerate(pipeline):
                    command = cmd_args[0]
                    args = cmd_args[1:]
                    stdin = None
                    stdout = None
                    if i == 0:
                        stdin = None
                    else:
                        prev_proc = processes[i-1]
                        if hasattr(prev_proc, 'stdout') and isinstance(prev_proc.stdout, StringIO):
                            prev_proc.stdout.seek(0)
                            pipe_input = prev_proc.stdout.read()
                            stdin = subprocess.PIPE
                        else:
                            stdin = prev_proc.stdout
                    if i == len(pipeline) - 1:
                        stdout = None
                    else:
                        stdout = subprocess.PIPE

                    if command in commands:
                        output_capture = StringIO()
                        if stdin is not None:
                            old_stdin = sys.stdin
                            sys.stdin = TextIOWrapper(stdin, encoding="utf-8")
                        try:
                            result = commands[command](*args)
                            if result is not None:
                                output_capture.write(result)
                        finally:
                            if stdin is not None:
                                sys.stdin = old_stdin
                                try:
                                    if hasattr(stdin, 'close'):
                                        stdin.close()
                                except Exception:
                                    pass
                        output_capture.seek(0)
                        class BuiltinProcess:
                            def __init__(self, stdout):
                                self.stdout = stdout
                        processes.append(BuiltinProcess(output_capture))
                    else:
                        try:
                            p = subprocess.Popen([command] + args, stdin=stdin, stdout=stdout, text=True)
                            if stdin == subprocess.PIPE and 'pipe_input' in locals():
                                p_output, p_error = p.communicate(input=pipe_input)
                                processes.append(p)
                            else:
                                processes.append(p)
                            if i > 0 and isinstance(processes[i-1], subprocess.Popen):
                                processes[i-1].stdout.close()
                        except FileNotFoundError:
                            print(f"{command}: command not found")
                            for proc in processes:
                                if hasattr(proc, 'terminate'):
                                    proc.terminate()
                            break
                else:
                    last_proc = processes[-1]
                    if isinstance(last_proc, subprocess.Popen):
                        out, err = last_proc.communicate()
                        if out:
                            print(out, end="")
                    elif hasattr(last_proc, 'stdout') and isinstance(last_proc.stdout, StringIO):
                        last_proc.stdout.seek(0)
                        print(last_proc.stdout.read(), end="")
                    continue

            # Handle 2>> redirection (stderr)                           
            if "2>>" in args:
                try:
                    output_index = args.index("2>>")
                    output_file = args[output_index + 1]
                    actual_args = args[:output_index]
                except (IndexError, ValueError):
                    print("Syntax error: expected file after '2>>'")
                    continue

                with open(output_file, 'a') as f:
                    if command in commands:
                        try:
                            result = commands[command](*actual_args)
                            if result:
                                print(result, end="")
                        except Exception as e:
                            f.write(str(e) + "\n")
                    else:
                        path = find_in_path(command)
                        if path:
                            subprocess.run(
                                [path] + actual_args,
                                stderr=f,
                                stdout=None,
                                text=True
                            )
                        else:
                            f.write(f"{command}: command not found\n")

            # Handle 2> redirection (stderr)
            elif "2>" in args:
                try:
                    output_index = args.index("2>")
                    output_file = args[output_index + 1]
                    actual_args = args[:output_index]
                except (IndexError, ValueError):
                    print("Syntax error: expected file after '2>'", end="")
                    continue

                with open(output_file, 'w') as f:
                    if command in commands:
                        try:
                            result = commands[command](*actual_args)
                            if result:
                                print(result, end="")
                        except Exception as e:
                            f.write(str(e) + "\n")
                    else:
                        path = find_in_path(command)
                        if path:
                            subprocess.run(
                                [path] + actual_args,
                                stderr=f,
                                stdout=None,
                                text=True
                            )
                        else:
                            f.write(f"{command}: command not found\n")

            # Handle >> or 1>> redirection (stdout)
            elif ">>" in args or "1>>" in args:
                redirect_symbol = ">>" if ">>" in args else "1>>"
                try:
                    output_index = args.index(redirect_symbol)
                    output_file = args[output_index + 1]
                    actual_args = args[:output_index]
                except (IndexError, ValueError):
                    print(f"Syntax error: expected file after '{redirect_symbol}'", end="")
                    continue

                with open(output_file, 'a') as f:
                    if command in commands:
                        result = commands[command](*actual_args)
                        f.write(result if result else "")
                    else:
                        path = find_in_path(command)
                        if path:
                            subprocess.run(
                                [path] + actual_args,
                                stdout=f,
                                stderr=None,
                                text=True
                            )
                        else:
                            f.write(f"{command}: command not found\n")
 
            # Handle > or 1> redirection (stdout)
            elif ">" in args or "1>" in args:
                redirect_symbol = ">" if ">" in args else "1>"
                try:
                    output_index = args.index(redirect_symbol)
                    output_file = args[output_index + 1]
                    actual_args = args[:output_index]
                except (IndexError, ValueError):
                    print(f"Syntax error: expected file after '{redirect_symbol}'")
                    continue

                with open(output_file, 'w') as f:
                    if command in commands:
                        result = commands[command](*actual_args)
                        f.write(result if result else "")
                    else:
                        path = find_in_path(command)
                        if path:
                            subprocess.run(
                                [path] + actual_args,
                                stdout=f,
                                stderr=None,
                                text=True
                            )
                        else:
                            f.write(f"{command}: command not found\n")
            

            # Built-in commands
            elif command in commands:
                result = commands[command](*args)
                if result is not None:
                    print(result, end="")

            # External commands
            else:
                path = find_in_path(command)
                if path:
                    try:
                        subprocess.run([command] + args, executable=path)
                    except Exception as e:
                        print(f"Error executing {command}: {e}")
                else:
                    # Reconstruct the full sentence (e.g., "delete", "all", "logs") -> "delete all logs"
                    full_query = command + " " + " ".join(args)
                    print(f"🤖 AI Thinking: '{full_query}'...")
                    
                    generated_cmd = ai_engine.get_command_from_text(full_query)
                    
                    if "Error" in generated_cmd:
                        print(generated_cmd)
                    else:
                        print(f"⚡ Executing: {generated_cmd}")
                        # Auto-execute
                        try:
                            result = subprocess.run(
                                generated_cmd,
                                shell=True,
                                capture_output=True,
                                text=True
                            )
                            if result.stdout:
                                print(result.stdout, end="")
                            if result.stderr:
                                print(result.stderr, end="")
                        except Exception as e:
                            print(f"Execution failed: {e}")

    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()