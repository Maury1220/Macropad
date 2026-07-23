# Seed Studio RP2040 Macro Pad UI

## Setup

1. Copy `main.py` onto your RP2040 board running CircuitPython.
2. Adjust `KEY_PINS`, encoder pins, and `KEY_ACTIVE_HIGH` in `main.py` to match your wiring.
3. Install PySerial and Keyboard on your PC:

```bash
python -m pip install pyserial
```

```bash
python -m pip install keyboard
```

4. Run the host UI:

```bash
python host_ui.py
```

## Host UI commands

- `s`: request current state
- `r`: reset encoder position
- `d`: toggle debug reporting
- `h`: show help
- `q`: quit
