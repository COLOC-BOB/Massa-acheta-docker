import json
import os

WATCHERS_CONFIG_FILE = "watchers_state/watchers_config.json"
DEFAULTS = {
    "rolls": True,
    "blocks": True,
    "balance": True,  
    "heartbeat": True
}

def load_watchers_config():
    if not os.path.exists(WATCHERS_CONFIG_FILE):
        save_watchers_config(DEFAULTS)
        return DEFAULTS.copy()
    with open(WATCHERS_CONFIG_FILE, "rt") as f:
        return json.load(f)

def save_watchers_config(config):
    with open(WATCHERS_CONFIG_FILE, "wt") as f:
        json.dump(config, f, indent=2)

def set_watcher_state(watcher_name, state):
    config = load_watchers_config()
    config[watcher_name] = state
    save_watchers_config(config)

def is_watcher_enabled(watcher_name):
    config = load_watchers_config()
    return config.get(watcher_name, True)
