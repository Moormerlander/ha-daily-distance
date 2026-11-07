from __future__ import annotations

from datetime import time

DOMAIN = "daily_distance"
CONF_SPEED_SENSOR = "speed_sensor"
CONF_SPEED_UNIT = "speed_unit"
CONF_MIN_SPEED = "min_speed"
CONF_RESET_TIME = "reset_time"

SPEED_UNIT_KMH = "km/h"
SPEED_UNIT_MPH = "mph"

DEFAULT_SPEED_UNIT = SPEED_UNIT_KMH
DEFAULT_MIN_SPEED = 1.0
DEFAULT_RESET_TIME = time(0, 0)
STORE_VERSION = 1
STORE_KEY_PREFIX = "daily_distance"
