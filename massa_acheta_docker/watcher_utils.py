# massa_acheta_docker/watcher_utils.py
import os
import json

def load_json_watcher(filename, default=None):
    if not os.path.exists(filename):
        return default if default is not None else {}
    with open(filename, "rt") as f:
        return json.load(f)

def save_json_watcher(filename, data):
    with open(filename, "wt") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
