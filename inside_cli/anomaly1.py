import psutil
import time
import csv
import numpy as np
import os
from datetime import datetime

# --- RECOMMENDED SETTINGS ---
SAMPLES_NEEDED = 300       # 5 minutes of data
INTERVAL = 1.0             # 1 second updates
PERCENTILE_THRESHOLD = 98  # Top 2% is the "Danger Zone"
CSV_FILE = "process_baselines.csv"
SUSTAINED_LIMIT = 5        # Must stay high for 5 seconds to alert

def get_current_cpu_map():
    """Returns a dictionary of {name: cpu_usage} for all processes."""
    data = {}
    for proc in psutil.process_iter(['name']):
        try:
            # interval=None makes it non-blocking
            cpu = proc.cpu_percent(interval=None)
            name = proc.info['name']
            if name and cpu is not None:
                # We group by name because PIDs change, but names are consistent
                if name not in data:
                    data[name] = []
                data[name].append(cpu)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return data

def run_learning_phase():
    print(f"--- INITIALIZING LEARNING PHASE ({SAMPLES_NEEDED}s) ---")
    print("Please use your computer normally during this time.")
    
    master_history = {}
    
    for i in range(SAMPLES_NEEDED):
        batch = get_current_cpu_map()
        for name, values in batch.items():
            if name not in master_history:
                master_history[name] = []
            master_history[name].extend(values)
        
        # Simple progress output
        if i % 10 == 0:
            print(f"Progress: {i}/{SAMPLES_NEEDED} samples collected...")
        time.sleep(INTERVAL)

    # Calculate baselines
    baselines = {}
    for name, history in master_history.items():
        if len(history) > 10: # Only baseline processes we saw enough of
            # 98th percentile for stability
            limit = np.percentile(history, PERCENTILE_THRESHOLD)
            # Ensure a minimum 5% floor so we don't alert on 1% -> 2% jumps
            baselines[name] = max(5.0, float(limit))
    
    save_baselines(baselines)
    return baselines

def save_baselines(baselines):
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ProcessName', 'MaxNormalCPU'])
        for name, val in baselines.items():
            writer.writerow([name, round(val, 2)])
    print(f"Baselines saved to {CSV_FILE}")

def load_baselines():
    if not os.path.exists(CSV_FILE):
        return None
    
    print(f"Loading existing baselines from {CSV_FILE}...")
    baselines = {}
    with open(CSV_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            baselines[row['ProcessName']] = float(row['MaxNormalCPU'])
    return baselines

def start_monitoring(baselines):
    print("\n--- MONITORING STARTING ---")
    print("Monitoring for sustained anomalies (Ctrl+C to stop)...")
    
    alert_trackers = {} # {name: consecutive_hits}
    
    try:
        while True:
            # Refresh CPU stats
            for proc in psutil.process_iter(['name']):
                try:
                    name = proc.info['name']
                    cpu = proc.cpu_percent(interval=None)
                    
                    if name in baselines:
                        threshold = baselines[name]
                        if cpu > threshold:
                            alert_trackers[name] = alert_trackers.get(name, 0) + 1
                            if alert_trackers[name] == SUSTAINED_LIMIT:
                                print(f"ALERT [{datetime.now().strftime('%H:%M:%S')}]: {name} is unusually high!")
                                print(f"      Current: {cpu}% | Baseline: {threshold}%")
                        else:
                            alert_trackers[name] = 0
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    # Pre-heat psutil
    psutil.cpu_percent(interval=None)
    
    # 1. Try to load existing data
    existing_baselines = load_baselines()
    
    if existing_baselines:
        choice = input("Baselines found. Re-learn? (y/n): ").lower()
        if choice == 'y':
            baselines = run_learning_phase()
        else:
            baselines = existing_baselines
    else:
        baselines = run_learning_phase()
    
    # 2. Monitor
    start_monitoring(baselines)