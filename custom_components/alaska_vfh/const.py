"""Constants for Alaska VFH integration."""

DOMAIN = "alaska_vfh"

# Register addresses (Modbus holding registers, FC03 read)
REG_DEVICE_ID = 0
REG_BAUD_RATE = 1
REG_SERIAL_FORMAT = 2
REG_RESERVED = 3
REG_SYSTEM_STATUS = 6
REG_FEEDBACK_STATUS = 7
REG_USAGE_HOURS = 8
REG_VENT24_REMAINING = 9
REG_MODE = 10
REG_WORK_TIME = 11

# Magic word for the reset registers (power board reset, filter message reset)
RESET_MAGIC = 0xAA55

# Default configuration
DEFAULT_PORT = 4196
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_WORK_TIME = 30

# Config flow keys
CONF_SLAVE_ID = "slave_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MODEL = "model"

# Device info
MANUFACTURER = "Alaska"

# Gateway communication
DEFAULT_REQUEST_GAP: float = 0.05  # seconds between consecutive requests on one gateway
REQUEST_TIMEOUT: float = 2  # seconds (a 9600 baud reply arrives in <100 ms)
REQUEST_RETRIES: int = 0

# The polled register block starts at register 6; its length depends on the model
POLL_START = REG_SYSTEM_STATUS

# Option bounds
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 60
