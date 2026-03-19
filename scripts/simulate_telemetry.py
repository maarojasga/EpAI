"""
simulate_telemetry.py - simulates a real-time sensor data stream from a CSV file.
Usage:
    python scripts/simulate_telemetry.py --file data/path_to_telemetry.csv --url http://localhost:8001/api/v1/telemetry/ingest --hz 1
"""
import time
import pandas as pd
import requests
import argparse
import json
from datetime import datetime


def simulate(file_path, url, hz):
    print(f"[*] Starting simulation from {file_path}")
    print(f"[*] Target URL: {url}")
    print(f"[*] Frequency: {hz} Hz")
    
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"[!] Error reading CSV: {e}")
        return

    delay = 1.0 / hz
    total_rows = len(df)
    
    for i, (_, row) in enumerate(df.iterrows()):
        # Convert row to dict, handling NaNs
        data = row.to_dict()
        for k, v in data.items():
            if pd.isna(v):
                data[k] = None
        
        # Send to API
        try:
            response = requests.post(url, json=data, timeout=2)
            if response.status_code == 200:
                result = response.json()
                alerts = result.get("alerts", [])
                if alerts:
                    print(f"\n[!] ALERT DETECTED at row {i+1}:")
                    for alert in alerts:
                        print(f"    - {alert['type']}: {alert['message']} (Device: {alert['device_id']}, Location: {alert['location']})")
                else:
                    print(".", end="", flush=True)
            else:
                print(f"\n[!] Error from API ({response.status_code}): {response.text}")
        except Exception as e:
            print(f"\n[!] Connection error: {e}")
            time.sleep(2)
        
        if (i + 1) % 50 == 0:
            print(f" [{i+1}/{total_rows}]")
            
        time.sleep(delay)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EpAI Telemetry Simulator")
    parser.add_argument("--file", required=True, help="Path to telemetry CSV")
    parser.add_argument("--url", default="http://localhost:8001/api/v1/telemetry/ingest", help="Ingest API URL")
    parser.add_argument("--hz", type=float, default=1.0, help="Simulation frequency in Hz")
    
    args = parser.parse_args()
    simulate(args.file, args.url, args.hz)
