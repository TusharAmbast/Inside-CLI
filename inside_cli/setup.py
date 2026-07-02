# inside_cli/setup.py

import ollama
import sys
import os
import requests
from pathlib import Path

# ── Configuration ──────────────────────────────────────────
MODEL_FILENAME = "qwen25_new_finetuned_q4_K_S.gguf"
CUSTOM_MODEL_NAME = "inside_model"
HF_URL = "https://huggingface.co/tusharr-04/Inside_cli/resolve/main/qwen25_new_finetuned_q4_K_S.gguf"

# Model will be saved here on the user's machine
MODEL_DIR = Path.home() / ".inside_cli" / "models"
MODEL_PATH = MODEL_DIR / MODEL_FILENAME
# ───────────────────────────────────────────────────────────


def check_ollama():
    """Check if Ollama is installed and running"""
    try:
        ollama.list()
        print("✅ Ollama found")
    except Exception:
        print("❌ Ollama is not running or not installed.")
        print("👉 Install from: https://ollama.com/download")
        print("   Then restart your terminal and run inside-cli again.")
        sys.exit(1)


def download_model():
    """Download model from Hugging Face if not already present"""
    if MODEL_PATH.exists():
        # Verify file size — if too small it's corrupted
        if MODEL_PATH.stat().st_size < 100 * 1024 * 1024:  # less than 100MB
            print("⚠️  Existing model file seems corrupted. Re-downloading...")
            MODEL_PATH.unlink()  # delete corrupt file
        else:
            print("✅ Model already downloaded")
            return

    print(f"⬇️  Downloading model ({MODEL_FILENAME}) ~896MB...")
    print("   This only happens once. Please wait...\n")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Use a session with retries for reliability
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    session.mount("https://", adapter)

    response = session.get(HF_URL, stream=True, timeout=60)
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))
    downloaded = 0

    # Write to temp file first, rename after complete download
    temp_path = MODEL_DIR / (MODEL_FILENAME + ".tmp")

    try:
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        percent = int(downloaded * 100 / total)
                        mb_done = downloaded / (1024 * 1024)
                        mb_total = total / (1024 * 1024)
                        print(f"   {percent}% ({mb_done:.1f}/{mb_total:.1f} MB)", end="\r")

        # Only rename to final name if download completed fully
        temp_path.rename(MODEL_PATH)
        print(f"\n✅ Model downloaded to {MODEL_PATH}")

    except Exception as e:
        # Clean up incomplete temp file on failure
        if temp_path.exists():
            temp_path.unlink()
        print(f"\n❌ Download failed: {e}")
        sys.exit(1)


def create_custom_model():
    """Create Ollama model using the downloaded .gguf and Modelfile"""
    installed = [m.model for m in ollama.list().models]

    if any(CUSTOM_MODEL_NAME in m for m in installed):
        print(f"✅ Model '{CUSTOM_MODEL_NAME}' already set up in Ollama")
        return

    print(f"⚙️  Setting up '{CUSTOM_MODEL_NAME}' in Ollama...")

    # Read Modelfile template
    modelfile_path = os.path.join(os.path.dirname(__file__), "Modelfile")
    with open(modelfile_path, "r") as f:
        modelfile_content = f.read()

    # Replace placeholder with actual downloaded path
    modelfile_content = modelfile_content.replace(
        "{MODEL_PATH}",
        str(MODEL_PATH).replace("\\", "/")
    )

    # Write resolved modelfile to a temp location
    temp_modelfile = MODEL_DIR / "Modelfile"
    with open(temp_modelfile, "w") as f:
        f.write(modelfile_content)

    # Use ollama CLI directly — most reliable across all versions
    import subprocess
    subprocess.run(
        ["ollama", "create", CUSTOM_MODEL_NAME, "-f", str(temp_modelfile)],
        check=True
    )

    print(f"✅ '{CUSTOM_MODEL_NAME}' ready in Ollama")


def run_setup():
    """Master setup — call this on every app startup"""
    print("🔧 Running setup checks...")
    check_ollama()
    download_model()
    create_custom_model()
    print("\n🚀 All set! Launching Inside CLI...\n")