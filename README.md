# Inside-CLI 🖥️

> A cross-platform intelligent shell — natural language to Bash/PowerShell, real-time process monitoring, and AI-powered anomaly detection. All from your terminal.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-lightgrey)
![LLM](https://img.shields.io/badge/LLM-Qwen--2.5%20Fine--tuned-orange)
![PyPI](https://img.shields.io/badge/PyPI-inside--cli-green?logo=pypi&logoColor=white)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

---

## What is Inside-CLI?

**Inside-CLI** is an AI-powered developer tool that gives you a smarter terminal experience. It combines a fine-tuned large language model with mathematical anomaly detection to let you:

- **Speak to your shell in plain English** — get Bash or PowerShell commands back instantly
- **Monitor system processes in real time** — with an interactive dashboard and scatter plot visualizations
- **Detect resource-hungry anomalies automatically** — powered by a custom detection algorithm and LLM-based process explainer

No more Googling commands. No more mysterious CPU spikes. Inside-CLI puts you in control.

---

## Features

### 🗣️ Natural Language → Shell Commands
Type what you want in plain English. Inside-CLI translates it into the correct Bash (macOS/Linux) or PowerShell (Windows) command — with **~90% accuracy**, powered by a fine-tuned **Qwen-2.5** model trained on 4 custom datasets.

```
> show me all running docker containers
docker ps

> find files larger than 100MB in my home directory
find ~ -type f -size +100M
```

### 📊 Real-Time Process Dashboard
An interactive CLI dashboard that visualizes all running system processes with **live scatter plots** — mapping CPU vs. memory usage so you can instantly see what's consuming your resources.

### 🚨 Anomaly Detection
A mathematical anomaly detection algorithm continuously monitors process behavior and flags anything with abnormal resource consumption. Abnormal processes are surfaced automatically — no manual digging required.

### 🤖 LLM-Based Process Explainer
Don't know what a process is? The built-in **Process Explainer** uses an LLM to give you a plain-English explanation of any flagged process — what it does, why it might be consuming resources, and whether you should be concerned.

---

## Installation

**Prerequisites:** Python 3.8+

```bash
pip install inside-cli
```

---

## Screenshots

### 📈 System Usage — Real-Time CPU, RAM & Disk Monitoring
![System Usage Dashboard](https://raw.githubusercontent.com/TusharAmbast/Inside-CLI/main/assets/system_usage.png)
> Live area chart tracking CPU (yellow), RAM (green), and Disk (dashed red) usage over time.

---

### 🔵 Scatter Plot — Process Visualization by User
![Scatter Plot](https://raw.githubusercontent.com/TusharAmbast/Inside-CLI/main/assets/scatter_plot.png)
> Each bubble represents a running process, clustered by user. Bubble size reflects resource consumption intensity.

---

### 🚨 Anomaly Detection — Flagged Processes with AI Verdict
![Anomaly Detection](https://raw.githubusercontent.com/TusharAmbast/Inside-CLI/main/assets/anomaly.png)
> Abnormal processes are listed with an AI-generated verdict — **green** means safe to remove for CPU relaxation, **red** means the process is critical and should not be terminated.

---

## How It Works

```
User Input (Natural Language)
        │
        ▼
┌───────────────────┐
│  Fine-tuned       │  ← Qwen-2.5, trained on 4 custom datasets
│  Qwen-2.5 LLM     │
└───────────────────┘
        │
        ▼
 Bash / PowerShell Command (cross-platform)

System Processes
        │
        ▼
┌───────────────────┐
│ Anomaly Detection │  ← Mathematical algorithm on CPU/memory metrics
│   Algorithm       │
└───────────────────┘
        │
   Flagged Process
        │
        ▼
┌───────────────────┐
│ LLM Process       │  ← Plain-English explanation of what's wrong
│   Explainer       │
└───────────────────┘
        │
        ▼
  Interactive Dashboard (real-time scatter plots)
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python |
| LLM | Qwen-2.5 (fine-tuned) |
| Training Data | 4 custom datasets |
| Process Monitoring | psutil |
| CLI Interface | Rich / Click |
| Visualization | Real-time scatter plots |
| Platform Support | macOS, Windows |

---

## Roadmap

- [ ] Linux support
- [ ] More LLM command categories (git, docker, kubernetes)
- [ ] Alert notifications for anomalous processes
- [ ] Export process reports to CSV/JSON
- [ ] Plugin system for custom anomaly rules

---

## Contributing

Contributions are welcome! Here's how to get started:

1. Fork the repository
2. Create a new branch
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Make your changes and commit
   ```bash
   git commit -m "feat: add your feature"
   ```
4. Push and open a Pull Request
   ```bash
   git push origin feature/your-feature-name
   ```

Please open an issue first for major changes so we can discuss what you'd like to change.

---

## Author

**Tushar Ambast**
- GitHub: [@TusharAmbast](https://github.com/TusharAmbast)

**Hritik Routia**
- GitHub: [@oghritik](https://github.com/oghritik)

---

## Acknowledgements

- [Qwen-2.5](https://github.com/QwenLM/Qwen2.5) by Alibaba Cloud for the base LLM
- [psutil](https://github.com/giampaolo/psutil) for cross-platform process utilities
- [Rich](https://github.com/Textualize/rich) for beautiful terminal interfaces

---

*Built with ❤️ for developers who live in the terminal.*
