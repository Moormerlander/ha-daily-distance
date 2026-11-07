from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import (
    CONF_MIN_SPEED,
    CONF_RESET_TIME,
    CONF_SPEED_SENSOR,
    CONF_SPEED_UNIT,
    SPEED_UNIT_KMH,
    STORE_KEY_PREFIX,
    STORE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class DailyDistanceManager:
    """Calculate distance from a Home Assistant speed sensor."""

    MAX_GAP_SECONDS = 300
    SAVE_INTERVAL_SECONDS = 30
    CALCULATION_INTERVAL = timedelta(seconds=1)
    MPH_TO_KMH = 1.609344

    def __init__(self, hass: HomeAssistant, entry_id: str, config: dict[str, Any]) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.speed_sensor = config[CONF_SPEED_SENSOR]
        self.speed_unit = config.get(CONF_SPEED_UNIT, SPEED_UNIT_KMH)
        self.min_speed = float(config[CONF_MIN_SPEED])
        self.reset_time = self._parse_time(config[CONF_RESET_TIME])
        self.store = Store(hass, STORE_VERSION, f"{STORE_KEY_PREFIX}.{entry_id}")
        self._unsub_interval: Callable[[], None] | None = None
        self._unsub_reset: Callable[[], None] | None = None
        self._listeners: list[Callable[[], None]] = []
        self._save_handle: Any = None
        self._last_calculation: float | None = None
        self._data: dict[str, Any] = {"days": {}, "total_km": 0.0}
        self._current_day: str | None = None

    @staticmethod
    def _parse_time(value: time | str) -> time:
        if isinstance(value, time):
            return value
        return time.fromisoformat(value)

    async def async_load(self) -> None:
        stored = await self.store.async_load()
        if isinstance(stored, dict):
            self._data.update(stored)
        self._data.setdefault("days", {})
        self._data.setdefault("total_km", 0.0)
        self._current_day = self._day_key(datetime.now().astimezone())
        self._prune_days()

    def _day_key(self, dt: datetime) -> str:
        local = dt.astimezone()
        boundary = local.replace(
            hour=self.reset_time.hour,
            minute=self.reset_time.minute,
            second=self.reset_time.second,
            microsecond=0,
        )
        if local < boundary:
            local -= timedelta(days=1)
        return local.date().isoformat()

    def _prune_days(self) -> None:
        days = self._data.setdefault("days", {})
        if len(days) > 400:
            for key in sorted(days)[:-400]:
                days.pop(key, None)

    async def async_start(self) -> None:
        self._unsub_interval = async_track_time_interval(
            self.hass, self._async_calculate, self.CALCULATION_INTERVAL
        )
        self._unsub_reset = async_track_time_change(
            self.hass,
            self._async_reset_tick,
            hour=self.reset_time.hour,
            minute=self.reset_time.minute,
            second=self.reset_time.second,
        )

    async def async_stop(self) -> None:
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
        if self._unsub_reset:
            self._unsub_reset()
            self._unsub_reset = None
        if self._save_handle:
            self._save_handle()
            self._save_handle = None
        await self.async_save()

    async def async_save(self) -> None:
        await self.store.async_save(self._data)

    def _schedule_save(self) -> None:
        if self._save_handle is not None:
            return

        async def _save_later(_now) -> None:
            self._save_handle = None
            await self.async_save()

        self._save_handle = self.hass.loop.call_later(
            self.SAVE_INTERVAL_SECONDS,
            lambda: self.hass.async_create_task(_save_later(None)),
        )

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener) if listener in self._listeners else None

    @callback
    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    async def _async_reset_tick(self, now: datetime) -> None:
        new_day = self._day_key(now)
        if new_day != self._current_day:
            self._current_day = new_day
            self._last_calculation = now.timestamp()
            await self.async_save()
            self._notify()

    async def _async_calculate(self, now: datetime) -> None:
        state = self.hass.states.get(self.speed_sensor)
        if state is None:
            self._last_calculation = None
            return

        try:
            speed = float(state.state)
        except (TypeError, ValueError):
            self._last_calculation = None
            return

        if speed < 0:
            self._last_calculation = None
            return

        timestamp = now.timestamp()
        if self._last_calculation is None:
            self._last_calculation = timestamp
            return

        elapsed = timestamp - self._last_calculation
        self._last_calculation = timestamp
        if elapsed <= 0 or elapsed > self.MAX_GAP_SECONDS:
            return

        day_key = self._day_key(now)
        if day_key != self._current_day:
            self._current_day = day_key
            await self.async_save()
            self._notify()
            return

        effective_speed = speed if speed >= self.min_speed else 0.0
        speed_kmh = effective_speed if self.speed_unit == SPEED_UNIT_KMH else effective_speed * self.MPH_TO_KMH
        distance_km = speed_kmh * elapsed / 3600.0
        if distance_km <= 0:
            return

        days = self._data.setdefault("days", {})
        days[day_key] = float(days.get(day_key, 0.0)) + distance_km
        self._data["total_km"] = float(self._data.get("total_km", 0.0)) + distance_km
        self._prune_days()
        self._schedule_save()
        self._notify()

    def _value_for_day(self, day_key: str) -> float:
        return float(self._data.get("days", {}).get(day_key, 0.0))

    def _day_keys(self, count: int) -> list[str]:
        current = datetime.fromisoformat(self._current_day) if self._current_day else datetime.now().astimezone()
        return [(current - timedelta(days=i)).date().isoformat() for i in range(count)]

    def value_today_km(self) -> float:
        return self._value_for_day(self._current_day or self._day_key(datetime.now().astimezone()))

    def value_yesterday_km(self) -> float:
        keys = self._day_keys(2)
        return self._value_for_day(keys[1])

    def value_period_km(self, days: int) -> float:
        return sum(self._value_for_day(key) for key in self._day_keys(days))

    def value_month_km(self, now: datetime | None = None) -> float:
        now = now or datetime.now().astimezone()
        return sum(self._value_for_day(day.isoformat()) for day in self._dates_between(now.date().replace(day=1), now.date()))

    def value_year_km(self, now: datetime | None = None) -> float:
        now = now or datetime.now().astimezone()
        start = now.date().replace(month=1, day=1)
        return sum(self._value_for_day(day.isoformat()) for day in self._dates_between(start, now.date()))

    @staticmethod
    def _dates_between(start, end):
        current = start
        while current <= end:
            yield current
            current += timedelta(days=1)

    def value_total_km(self) -> float:
        return float(self._data.get("total_km", 0.0))

    def to_output_distance(self, km: float) -> float:
        return km if self.speed_unit == SPEED_UNIT_KMH else km / self.MPH_TO_KMH

    def daily_values(self, days: int = 30) -> dict[str, float]:
        keys = list(reversed(self._day_keys(days)))
        return {key: round(self.to_output_distance(self._value_for_day(key)), 3) for key in keys}
