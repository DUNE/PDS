"""
Project-wide immutable constants.
Feel free to extend, but keep it import-light.
"""

# All supported DAPHNE configuration names
CONFIGURATIONS: list[str] = [
    "np02_daphne_full_mode",
    "np02_daphne_full_mode_bias_off",
    "np02_daphne_selftrigger",
    "np02_daphne_selftrigger_bias_off",
]

# Default JSON pretty-printer indent
JSON_INDENT: int = 2

# Channels per AFE on NP02 boards
CHANNELS_PER_AFE: int = 8
