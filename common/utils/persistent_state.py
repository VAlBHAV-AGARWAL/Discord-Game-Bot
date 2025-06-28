import json
import os
import threading

_state_locks = {}

def _get_lock(filename):
    if filename not in _state_locks:
        _state_locks[filename] = threading.Lock()
    return _state_locks[filename]

def load_state(filename, default=None):
    """
    Load persistent state from a JSON file. Returns default if file does not exist or is invalid.
    """
    lock = _get_lock(filename)
    with lock:
        if not os.path.exists(filename):
            return default if default is not None else {}
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return default if default is not None else {}

def save_state(filename, data):
    """
    Save persistent state to a JSON file.
    """
    lock = _get_lock(filename)
    with lock:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def get_value(filename, key, default=None):
    """
    Get a value from the persistent state file.
    """
    state = load_state(filename)
    return state.get(key, default)

def set_value(filename, key, value):
    """
    Set a value in the persistent state file.
    """
    state = load_state(filename)
    state[key] = value
    save_state(filename, state)

def delete_value(filename, key):
    """
    Delete a value from the persistent state file.
    """
    state = load_state(filename)
    if key in state:
        del state[key]
        save_state(filename, state)

async def send_critical_error(bot, msg):
    """
    Async handler for critical errors. Logs and optionally sends to a channel.
    """
    print(f"CRITICAL ERROR: {msg}")
    # Optionally, send to a Discord channel or DM the owner here

def check_sharding_safety():
    """
    Check if persistent state is safe for sharding (stub implementation).
    Returns True if safe, False otherwise.
    """
    # Implement actual sharding safety checks if needed
    return True
