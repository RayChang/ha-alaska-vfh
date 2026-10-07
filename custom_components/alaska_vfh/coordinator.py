"""Data update coordinator for Alaska VFH."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WORK_TIME,
    DOMAIN,
    INFO_COUNT,
    MANUFACTURER,
    MIN_WORK_MINUTES,
    MODE_MAX_MINUTES,
    MODE_OFF,
    MODE_VENT_24H,
    MODEL,
    MODES,
    MODES_FC06,
    POLL_COUNT,
    POLL_START,
    REG_FIRMWARE_VERSION,
    REG_MODE,
    REG_RESET,
    RESET_MAGIC,
    VENT24_MINUTES,
)
from .hub import AlaskaHub, AlaskaHubError

_LOGGER = logging.getLogger(__name__)

type AlaskaConfigEntry = ConfigEntry[AlaskaCoordinator]

MAX_WORK_MINUTES = max(MODE_MAX_MINUTES.values())


@dataclass(frozen=True, slots=True)
class HeaterState:
    """Decoded snapshot of registers 6..11."""

    system_status: int
    feedback_status: int
    usage_hours: int
    vent24_remaining: int
    mode: int
    work_time_raw: int

    @property
    def remaining_minutes(self) -> int:
        """Minutes left in the running mode.

        Mode 7 counts down in register 9; timed modes 1-6 use register 11
        (hi byte hours, lo byte minutes); any other mode (off) has none.
        """
        if self.mode == MODE_VENT_24H:
            return self.vent24_remaining
        if self.mode in MODE_MAX_MINUTES:
            return (self.work_time_raw >> 8) * 60 + (self.work_time_raw & 0xFF)
        return 0


def encode_work_time(minutes: int) -> int:
    """Encode minutes as register 11 value: hours * 256 + minutes."""
    return (minutes // 60) * 256 + minutes % 60


def format_firmware(register: int) -> str:
    """Format register 4 (hi byte major, lo byte minor), e.g. 0x020B -> 2.11."""
    return f"{register >> 8}.{register & 0xFF}"


def _translated_error(err: AlaskaHubError, *, write: bool) -> HomeAssistantError:
    """Build a HomeAssistantError carrying a translation key and the error code."""
    if err.kind == "timeout":
        key, placeholders = "timeout", {}
    elif err.kind == "modbus":
        key = "write_failed" if write else "modbus_exception"
        placeholders = {"code": str(err.code)}
    else:
        key, placeholders = "communication_error", {"error": str(err)}
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders,
    )


class AlaskaCoordinator(DataUpdateCoordinator[HeaterState]):
    """Poll one heater and perform writes on it."""

    config_entry: AlaskaConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: AlaskaConfigEntry, hub: AlaskaHub
    ) -> None:
        """Create the coordinator for a config entry."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=1.0, immediate=True
            ),
        )
        self.hub = hub
        self.slave_id: int = entry.data[CONF_SLAVE_ID]
        self.work_time: int = DEFAULT_WORK_TIME
        self.firmware: str | None = None
        self.raw_registers: dict[int, int] = {}
        self._write_lock = asyncio.Lock()

    @property
    def device_info(self) -> DeviceInfo:
        """Device shared by all entities of this entry."""
        entry = self.config_entry
        return DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=self.firmware,
        )

    async def async_read_device_info(self) -> None:
        """Read the identification registers 0..5 once (firmware version)."""
        try:
            registers = await self.hub.async_read_holding_registers(
                0, INFO_COUNT, self.slave_id
            )
        except AlaskaHubError as err:
            raise _translated_error(err, write=False) from err
        self.firmware = format_firmware(registers[REG_FIRMWARE_VERSION])

    async def _async_read_state(self) -> HeaterState:
        """Read registers 6..11 in a single request and decode them."""
        registers = await self.hub.async_read_holding_registers(
            POLL_START, POLL_COUNT, self.slave_id
        )
        self.raw_registers = {
            POLL_START + i: value for i, value in enumerate(registers)
        }
        return HeaterState(*registers)

    async def _async_update_data(self) -> HeaterState:
        """Poll the heater."""
        try:
            return await self._async_read_state()
        except AlaskaHubError as err:
            translated = _translated_error(err, write=False)
            raise UpdateFailed(
                translation_domain=translated.translation_domain,
                translation_key=translated.translation_key,
                translation_placeholders=translated.translation_placeholders,
            ) from err

    async def async_set_mode(self, mode: int, minutes: int | None = None) -> None:
        """Select a work mode (see _async_set_mode for the FC06/FC16 rule)."""
        async with self._write_lock:
            await self._async_set_mode(mode, minutes)

    async def _async_set_mode(self, mode: int, minutes: int | None) -> None:
        """Write a work mode.

        This is the single place where the write function code is chosen:
        modes 7 and 12 use FC06 (write_register); modes 1-6 use FC16
        (write_registers) with [mode, work_time], work_time clamped to
        [1, MODE_MAX_MINUTES[mode]] and encoded as hours * 256 + minutes.
        """
        if mode not in MODES:
            raise ValueError(f"Unsupported mode {mode}")
        work_time_raw: int | None = None
        if mode in MODES_FC06:
            await self._async_write(
                self.hub.async_write_register(REG_MODE, mode, self.slave_id), mode
            )
        else:
            wanted = self.work_time if minutes is None else minutes
            clamped = max(MIN_WORK_MINUTES, min(wanted, MODE_MAX_MINUTES[mode]))
            work_time_raw = encode_work_time(clamped)
            await self._async_write(
                self.hub.async_write_registers(
                    REG_MODE, [mode, work_time_raw], self.slave_id
                ),
                mode,
            )
        if self.data is not None:
            # Show the new mode and its time fields immediately, not after the poll
            if mode == MODE_VENT_24H:
                vent24, raw = VENT24_MINUTES, self.data.work_time_raw
            else:
                vent24, raw = 0, work_time_raw or 0
            self.async_set_updated_data(
                replace(
                    self.data, mode=mode, vent24_remaining=vent24, work_time_raw=raw
                )
            )
        await self.async_request_refresh()

    async def async_stop(self) -> None:
        """Stop the heater (mode 12)."""
        await self.async_set_mode(MODE_OFF)

    async def async_set_work_time(self, minutes: int) -> None:
        """Store the work time; push it only if the device is running a timed mode.

        The decision uses a fresh read of the device, never the last polled
        state, so a stopped heater is not restarted by a stale mode value.
        """
        wanted = max(MIN_WORK_MINUTES, min(minutes, MAX_WORK_MINUTES))
        async with self._write_lock:
            try:
                state = await self._async_read_state()
            except AlaskaHubError as err:
                raise _translated_error(err, write=False) from err
            self.async_set_updated_data(state)
            if state.mode in MODE_MAX_MINUTES:
                await self._async_set_mode(state.mode, wanted)
            self.work_time = wanted
        self.async_update_listeners()

    async def async_reset(self) -> None:
        """Reset the power board (only accepted by the device while stopped)."""
        await self._async_write(
            self.hub.async_write_register(REG_RESET, RESET_MAGIC, self.slave_id),
            None,
        )
        await self.async_request_refresh()

    async def _async_write(
        self, write: Coroutine[Any, Any, None], mode: int | None
    ) -> None:
        """Await a hub write and translate failures."""
        try:
            await write
        except AlaskaHubError as err:
            _LOGGER.warning(
                "Write to %s (slave %s, mode %s) failed: %s (exception code %s)",
                self.config_entry.title,
                self.slave_id,
                mode,
                err,
                err.code,
            )
            raise _translated_error(err, write=True) from err
