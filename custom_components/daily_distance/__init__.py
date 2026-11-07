from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import DailyDistanceManager

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = DailyDistanceManager(hass, entry.entry_id, entry.data)
    await manager.async_load()
    await manager.async_start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager: DailyDistanceManager = hass.data[DOMAIN].pop(entry.entry_id)
    await manager.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
