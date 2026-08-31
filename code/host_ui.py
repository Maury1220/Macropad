import json
import os
import queue
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("PySerial is required. Install it with: pip install pyserial")
    sys.exit(1)

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

CONFIG_FILE = Path(__file__).with_name("keybinds.json")
STATE_QUEUE: "queue.Queue[dict]" = queue.Queue()
LAST_STATE: dict | None = None
EVENT_DISPATCH = True

DEFAULT_BINDINGS = {
    "key_0": {"type": "print", "value": "Key 1 pressed"},
    "key_1": {"type": "print", "value": "Key 2 pressed"},
    "key_2": {"type": "print", "value": "Key 3 pressed"},
    "key_3": {"type": "print", "value": "Key 4 pressed"},
    "key_4": {"type": "print", "value": "Key 5 pressed"},
    "key_5": {"type": "print", "value": "Key 6 pressed"},
    "key_6": {"type": "print", "value": "Key 7 pressed"},
    "key_7": {"type": "print", "value": "Key 8 pressed"},
    "key_8": {"type": "print", "value": "Key 9 pressed"},
    "encoder_button": {"type": "print", "value": "Encoder button pressed"},
    "encoder_cw": {"type": "print", "value": "Encoder rotated clockwise"},
    "encoder_ccw": {"type": "print", "value": "Encoder rotated counter-clockwise"},
}

ACTION_TYPES = ["print", "command", "open", "shortcut", "none"]


def find_port():
    ports = list_ports.comports()
    if not ports:
        print("No serial ports found. Attach the RP2040 and try again.")
        return None

    candidates = [p.device for p in ports if "CircuitPython" in (p.description or "") or "USB Serial" in (p.description or "")]
    if len(candidates) == 1:
        return candidates[0]

    print("Available serial ports:")
    for idx, port in enumerate(ports, start=1):
        print(f"  {idx}: {port.device} - {port.description}")

    selection = input("Choose port number: ").strip()
    if not selection.isdigit() or int(selection) < 1 or int(selection) > len(ports):
        print("Invalid selection.")
        return None

    return ports[int(selection) - 1].device


def load_bindings():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
                bindings = json.load(handle)
                if isinstance(bindings, dict):
                    return bindings
        except Exception as exc:
            print("Failed to load keybinds.json:", exc)

    save_bindings(DEFAULT_BINDINGS)
    return DEFAULT_BINDINGS.copy()


def save_bindings(bindings):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
            json.dump(bindings, handle, indent=2)
    except Exception as exc:
        print("Failed to save keybinds.json:", exc)


def format_binding(key, binding):
    return f"{key}: {binding.get('type', 'none')} -> {binding.get('value', '')}"


def print_bindings(bindings):
    print("\n=== Current Bindings ===")
    for key in sorted(bindings, key=lambda name: (0 if name.startswith("key_") else 1, name)):
        print("  " + format_binding(key, bindings[key]))
    print("========================")


def pretty_print_state(payload):
    keys = payload.get("keys", [])
    encoder = payload.get("encoder_position", 0)
    button = payload.get("encoder_button", 0)

    rows = []
    for i in range(0, len(keys), 3):
        row = " ".join("[X]" if keys[j] else "[ ]" for j in range(i, min(i + 3, len(keys))))
        rows.append(row)

    print("\n=== RP2040 Macro Pad State ===")
    print("Keys:")
    for row in rows:
        print("  " + row)
    print(f"Encoder position: {encoder}")
    print(f"Encoder button: {'PRESSED' if button else 'released'}")
    print("=============================")


def execute_action(binding):
    if not binding or binding.get("type") == "none":
        return

    action_type = binding.get("type")
    value = binding.get("value", "")
    print(f"Action: {action_type} -> {value}")

    if action_type == "print":
        print(value)
        return

    if action_type == "open":
        try:
            webbrowser.open(value)
        except Exception as exc:
            print("Failed to open:", exc)
        return

    if action_type == "command":
        try:
            subprocess.Popen(value, shell=True)
        except Exception as exc:
            print("Failed to run command:", exc)
        return

    if action_type == "shortcut":
        if not KEYBOARD_AVAILABLE:
            print("Keyboard shortcut support requires the 'keyboard' package.")
            print("Install with: pip install keyboard")
            return
        try:
            keyboard.send(value)
        except Exception as exc:
            print("Failed to send shortcut:", exc)
        return

    print("Unknown action type:", action_type)


def process_state(payload, bindings):
    global LAST_STATE
    if LAST_STATE is None:
        LAST_STATE = payload
        return

    keys = payload.get("keys", [])
    old_keys = LAST_STATE.get("keys", [])
    for idx, pressed in enumerate(keys):
        if idx < len(old_keys) and pressed and not old_keys[idx]:
            execute_action(bindings.get(f"key_{idx}", {}))

    current_button = bool(payload.get("encoder_button", 0))
    old_button = bool(LAST_STATE.get("encoder_button", 0))
    if current_button and not old_button:
        execute_action(bindings.get("encoder_button", {}))

    current_encoder = int(payload.get("encoder_position", 0))
    old_encoder = int(LAST_STATE.get("encoder_position", 0))
    delta = current_encoder - old_encoder
    if delta > 0:
        execute_action(bindings.get("encoder_cw", {}))
    elif delta < 0:
        execute_action(bindings.get("encoder_ccw", {}))

    LAST_STATE = payload


def serial_reader(ser, stop_event):
    while not stop_event.is_set():
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
        except Exception:
            continue
        if not line:
            continue
        if line.startswith("STATE:"):
            payload = line[len("STATE:") :]
            try:
                state = json.loads(payload)
                STATE_QUEUE.put(state)
            except json.JSONDecodeError:
                print("Invalid state payload:", payload)
        else:
            print(line)


def print_help():
    print("\nCommands:")
    print("  s       - Request a fresh state snapshot")
    print("  r       - Reset encoder position")
    print("  d       - Toggle board debug/state reporting")
    print("  l       - List current bindings")
    print("  e       - Edit a binding")
    print("  t       - Toggle local action dispatch")
    print("  p       - Print the latest state snapshot")
    print("  h       - Print this help text")
    print("  q       - Quit")


def choose_binding_key():
    keys = list(DEFAULT_BINDINGS.keys())
    print("Available bindings:")
    for name in keys:
        print(f"  {name}")
    choice = input("Binding name: ").strip()
    if choice not in keys:
        print("Invalid binding name.")
        return None
    return choice


def edit_binding(bindings):
    key_name = choose_binding_key()
    if key_name is None:
        return

    binding = bindings.get(key_name, {"type": "none", "value": ""})
    print(f"Current: {format_binding(key_name, binding)}")
    action_type = input(f"Action type ({'/'.join(ACTION_TYPES)}): ").strip().lower()
    if action_type not in ACTION_TYPES:
        print("Invalid action type.")
        return

    value = ""
    if action_type != "none":
        value = input("Action value: ").strip()

    bindings[key_name] = {"type": action_type, "value": value}
    save_bindings(bindings)
    print("Binding updated.")


def process_pending_state(bindings):
    while True:
        try:
            payload = STATE_QUEUE.get_nowait()
        except queue.Empty:
            break
        pretty_print_state(payload)
        if EVENT_DISPATCH:
            process_state(payload, bindings)


def main():
    bindings = load_bindings()
    port = find_port()
    if not port:
        return

    try:
        ser = serial.Serial(port, 115200, timeout=0.1)
    except serial.SerialException as exc:
        print(f"Failed to open serial port {port}: {exc}")
        return

    stop_event = threading.Event()
    thread = threading.Thread(target=serial_reader, args=(ser, stop_event), daemon=True)
    thread.start()

    print_help()
    if not KEYBOARD_AVAILABLE:
        print("Keyboard shortcuts require the 'keyboard' package: pip install keyboard")

    while True:
        process_pending_state(bindings)
        try:
            command = input("> ").strip().lower()
        except KeyboardInterrupt:
            command = "q"

        if command == "q":
            break
        elif command == "h":
            print_help()
        elif command == "s":
            ser.write(b"s\n")
        elif command == "r":
            ser.write(b"r\n")
        elif command == "d":
            ser.write(b"d\n")
        elif command == "l":
            print_bindings(bindings)
        elif command == "e":
            edit_binding(bindings)
        elif command == "t":
            global EVENT_DISPATCH
            EVENT_DISPATCH = not EVENT_DISPATCH
            print(f"Local action dispatch {'enabled' if EVENT_DISPATCH else 'disabled'}.")
        elif command == "p":
            if LAST_STATE is not None:
                pretty_print_state(LAST_STATE)
            else:
                print("No state snapshot has arrived yet.")
        elif command:
            print("Unknown command. Type h for help.")

    stop_event.set()
    ser.close()
    print("Disconnected.")


if __name__ == "__main__":
    main()
