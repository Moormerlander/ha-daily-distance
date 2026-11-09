from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_FUEL_CONSUMPTION,
    CONF_FUEL_PRICE,
    CONF_MIN_SPEED,
    CONF_RESET_TIME,
    CONF_SPEED_SENSOR,
    CONF_SPEED_UNIT,
    DEFAULT_FUEL_CONSUMPTION,
    DEFAULT_FUEL_PRICE,
    DEFAULT_MIN_SPEED,
    DEFAULT_RESET_TIME,
    DEFAULT_SPEED_UNIT,
    DOMAIN,
    SPEED_UNIT_KMH,
    SPEED_UNIT_MPH,
)

CONF_SPEED_SENSOR_MANUAL = "speed_sensor_manual"


class DailyDistanceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            validated = self._validate_input(user_input, errors)
            if validated is not None:
                speed_sensor, data = validated
                await self.async_set_unique_id(f"{DOMAIN}_{speed_sensor}")
                self._abort_if_unique_id_configured()
                title = data.get("name") or "Daily Distance"
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            validated = self._validate_input(user_input, errors)
            if validated is not None:
                speed_sensor, data = validated
                new_unique_id = f"{DOMAIN}_{speed_sensor}"
                existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, new_unique_id
                )
                if existing is not None and existing.entry_id != entry.entry_id:
                    errors[CONF_SPEED_SENSOR] = "already_configured"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=new_unique_id,
                        data=data,
                        title=data.get("name") or "Daily Distance",
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._schema(entry.data, entry.title),
            errors=errors,
        )

    @staticmethod
    def _schema(
        current: dict[str, Any] | None = None,
        current_title: str | None = None,
    ) -> vol.Schema:
        current = current or {}
        current_speed_sensor = current.get(CONF_SPEED_SENSOR, "")
        current_speed_unit = current.get(CONF_SPEED_UNIT, DEFAULT_SPEED_UNIT)
        current_min_speed = float(current.get(CONF_MIN_SPEED, DEFAULT_MIN_SPEED))
        current_reset_time = current.get(
            CONF_RESET_TIME, DEFAULT_RESET_TIME.strftime("%H:%M:%S")
        )
        current_fuel_price = float(current.get(CONF_FUEL_PRICE, DEFAULT_FUEL_PRICE))
        current_fuel_consumption = float(
            current.get(CONF_FUEL_CONSUMPTION, DEFAULT_FUEL_CONSUMPTION)
        )
        if hasattr(current_reset_time, "strftime"):
            current_reset_time = current_reset_time.strftime("%H:%M:%S")

        return vol.Schema(
            {
                vol.Required(
                    "name", default=current.get("name", current_title or "Daily Distance")
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_SPEED_SENSOR, default=current_speed_sensor
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_SPEED_SENSOR_MANUAL, default=""): selector.TextSelector(),
                vol.Required(
                    CONF_SPEED_UNIT, default=current_speed_unit
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[SPEED_UNIT_KMH, SPEED_UNIT_MPH],
                        translation_key="speed_unit",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_MIN_SPEED, default=current_min_speed
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=20,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_RESET_TIME, default=current_reset_time
                ): selector.TimeSelector(),
                vol.Required(
                    CONF_FUEL_PRICE, default=current_fuel_price
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=10,
                        step=0.01,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_FUEL_CONSUMPTION, default=current_fuel_consumption
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=50,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    @classmethod
    def _validate_input(
        cls, user_input: dict[str, Any], errors: dict[str, str]
    ) -> tuple[str, dict[str, Any]] | None:
        selected = (user_input.get(CONF_SPEED_SENSOR) or "").strip()
        manual = (user_input.get(CONF_SPEED_SENSOR_MANUAL) or "").strip()

        if selected and manual:
            errors[CONF_SPEED_SENSOR_MANUAL] = "both_sensors"
            return None

        speed_sensor = selected or manual
        if not cls._valid_sensor_entity(speed_sensor):
            errors[CONF_SPEED_SENSOR] = "invalid_sensor"
            return None

        data = dict(user_input)
        data.pop(CONF_SPEED_SENSOR_MANUAL, None)
        data[CONF_SPEED_SENSOR] = speed_sensor
        return speed_sensor, data

    @staticmethod
    def _valid_sensor_entity(entity_id: str) -> bool:
        if not entity_id or "." not in entity_id:
            return False
        domain, object_id = entity_id.split(".", 1)
        return domain == "sensor" and bool(object_id)
