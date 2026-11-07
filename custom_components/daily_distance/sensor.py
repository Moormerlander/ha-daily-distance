from __future__ import annotations

from typing import Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, SPEED_UNIT_KMH
from .coordinator import DailyDistanceManager


SENSORS = (
    ("today", "today"),
    ("yesterday", "yesterday"),
    ("week", "week"),
    ("month", "month"),
    ("year", "year"),
    ("total", "total"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    manager: DailyDistanceManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DailyDistanceSensor(manager, entry, key) for key, _ in SENSORS])


class DailyDistanceSensor(SensorEntity):
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_icon = "mdi:map-marker-distance"
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, manager: DailyDistanceManager, entry: ConfigEntry, key: str) -> None:
        self.manager = manager
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING if key == "total" else SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "km" if manager.speed_unit == SPEED_UNIT_KMH else "mi"
        self._remove_listener: Callable[[], None] | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            translation_key="device",
        )

    async def async_added_to_hass(self) -> None:
        self._remove_listener = self.manager.add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

    @property
    def native_value(self) -> float:
        if self._attr_translation_key == "today":
            value = self.manager.value_today_km()
        elif self._attr_translation_key == "yesterday":
            value = self.manager.value_yesterday_km()
        elif self._attr_translation_key == "week":
            value = self.manager.value_period_km(7)
        elif self._attr_translation_key == "month":
            value = self.manager.value_month_km()
        elif self._attr_translation_key == "year":
            value = self.manager.value_year_km()
        else:
            value = self.manager.value_total_km()
        return round(self.manager.to_output_distance(value), 3)

    @property
    def extra_state_attributes(self):
        return {
            "speed_sensor": self.manager.speed_sensor,
            "speed_unit": self.manager.speed_unit,
            "minimum_speed": self.manager.min_speed,
            "reset_time": self.manager.reset_time.strftime("%H:%M:%S"),
            **({"daily_values_last_30_days": self.manager.daily_values(30)} if self._attr_translation_key == "today" else {}),
        }

    def _handle_update(self) -> None:
        self.async_write_ha_state()
