"""Constants for Alaska VFH integration."""

DOMAIN = "alaska_vfh"

# Register addresses (Modbus holding registers, FC03 read)
REG_DEVICE_ID = 0
REG_BAUD_RATE = 1
REG_SERIAL_FORMAT = 2
REG_RESERVED = 3
REG_FIRMWARE_VERSION = 4
REG_HEATER_ELEMENT_TYPE = 5
REG_SYSTEM_STATUS = 6
REG_FEEDBACK_STATUS = 7
REG_USAGE_HOURS = 8
REG_VENT24_REMAINING = 9
REG_MODE = 10
REG_WORK_TIME = 11
REG_RESET = 12

# Work modes (from manual §1, 300BKP)
MODES: dict[int, str] = {
    1: "heat_high",
    2: "heat_dry",
    3: "cool_fast",
    4: "dry_eco",
    5: "vent_high",
    6: "vent_low",
    7: "vent_24h",
    12: "off",
}

# Mode value that stops the heater
MODE_OFF: int = 12
# Mode value for 24 h continuous ventilation (countdown lives in register 9)
MODE_VENT_24H: int = 7
VENT24_MINUTES: int = 1440

# Modes that use FC06 (write_register); others require FC16 (write_registers)
MODES_FC06: frozenset[int] = frozenset({7, 12})

# Reset magic word (write to REG_RESET to trigger reset)
RESET_MAGIC = 0xAA55

# Work time limits per mode (minutes). From manual p.6 (PDF p.7), register 11 note:
# Modes 1–6 have a maximum of 8 hours (0800 in register format) = 480 minutes.
# Mode 7 (24h ventilation) is written only via FC06 without a time value (read-only).
# Mode 12 (off) is written only via FC06 without a time value.
MODE_MAX_MINUTES: dict[int, int] = {
    1: 480,
    2: 480,
    3: 480,
    4: 480,
    5: 480,
    6: 480,
}

# Default configuration
DEFAULT_PORT = 4196
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_WORK_TIME = 30
DEFAULT_NAME = "Alaska 300BKP"

# Config flow keys
CONF_SLAVE_ID = "slave_id"
CONF_SCAN_INTERVAL = "scan_interval"

# Device info
MANUFACTURER = "Alaska"
MODEL = "300BKP"

# Status register decoding (register value -> option key)
SYSTEM_STATUS: dict[int, str] = {0: "ok", 1: "temp_sensor_open", 2: "overheat"}
FEEDBACK_STATUS: dict[int, str] = {0: "ok", 1: "relay_fault", 2: "motor_open"}

# Gateway communication
DEFAULT_REQUEST_GAP: float = 0.05  # seconds between consecutive requests on one gateway
REQUEST_TIMEOUT: float = 2  # seconds (a 9600 baud reply arrives in <100 ms)
REQUEST_RETRIES: int = 0

# Polled register block: registers 6..11 are read in a single request
POLL_START = REG_SYSTEM_STATUS
POLL_COUNT = REG_WORK_TIME - REG_SYSTEM_STATUS + 1

# Registers 0..5 (identification block) are read once during setup
INFO_COUNT = REG_HEATER_ELEMENT_TYPE + 1

# Option bounds
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 60
MIN_WORK_MINUTES = 1
