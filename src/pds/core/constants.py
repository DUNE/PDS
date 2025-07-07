"""
Project-wide immutable constants.
Feel free to extend, but keep it import-light.
"""

# All supported DAPHNE configuration names
CONFIGURATIONS: list[str] = [
    "np02_daphne_selftrigger",
    "np02_daphne_fullstream",
]

ALWAYS_SELF_TRIGGER_IPS: set[str] = {"10.73.137.107"}
NEVER_BIAS_IPS: set[str] = {"10.73.137.106", "10.73.137.110"}

# Default JSON pretty-printer indent
JSON_INDENT: int = 2

# Channels per AFE on NP02 boards
CHANNELS_PER_AFE: int = 8
