from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_MIN_SPEED,
    CONF_RESET_TIME,
    CONF_SPEED_SENSOR,
    CONF_SPEED_UNIT,
    DEFAULT_MIN_SPEED,
    DEFAULT_RESET_TIME,
    DEFAULT_SPEED_UNIT,
    DOMAIN,
    SPEED_UNIT_KMH,
    SPEED_UNIT_MPH,
)

CONF_SPEED_SENSOR_MANUAL = "speed_sensor_manual"


class TageskilometerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = (user_input.get(CONF_SPEED_SENSOR) or "").strip()
            manual = (user_input.get(CONF_SPEED_SENSOR_MANUAL) or "").strip()

            if selected and manual:
                errors[CONF_SPEED_SENSOR_MANUAL] = "both_sensors"
            else:
                speed_sensor = selected or manual
                if not self._valid_sensor_entity(speed_sensor):
                    errors[CONF_SPEED_SENSOR] = "invalid_sensor"
                else:
                    data = dict(user_input)
                    data.pop(CONF_SPEED_SENSOR_MANUAL, None)
                    data[CONF_SPEED_SENSOR] = speed_sensor
                    await self.async_set_unique_id(f"{DOMAIN}_{speed_sensor}")
                    self._abort_if_unique_id_configured()
                    title = data.get("name") or "Daily Distance"
                    return self.async_create_entry(title=title, data=data)

        schema = vol.Schema(
            {
                vol.Required("name", default="Daily Distance"): selector.TextSelector(),
                vol.Optional(CONF_SPEED_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_SPEED_SENSOR_MANUAL, default=""): selector.TextSelector(),
                vol.Required(CONF_SPEED_UNIT, default=DEFAULT_SPEED_UNIT): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[SPEED_UNIT_KMH, SPEED_UNIT_MPH],
                        translation_key="speed_unit",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_MIN_SPEED, default=DEFAULT_MIN_SPEED): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=20,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_RESET_TIME, default=DEFAULT_RESET_TIME.strftime("%H:%M:%S")
                ): selector.TimeSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def _valid_sensor_entity(entity_id: str) -> bool:
        if not entity_id or "." not in entity_id:
            return False
        domain, object_id = entity_id.split(".", 1)
        return domain == "sensor" and bool(object_id)
