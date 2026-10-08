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
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WORK_TIME,
    DOMAIN,
    MANUFACTURER,
    POLL_START,
    REG_MODE,
    REG_USAGE_HOURS,
    RESET_MAGIC,
)
from .hub import AlaskaHub, AlaskaHubError
from .models import (
    AIR_DIRECTIONS,
    AIR_ZONES,
    INFO_BLOCK_COUNT,
    MIN_WORK_MINUTES,
    REG_AIR_DIRECTION,
    REG_AIR_ZONE,
    REG_HEATER_TYPE,
    VENT24_MINUTES,
    get_profile,
    plan_mode_write,
)

_LOGGER = logging.getLogger(__name__)

type AlaskaConfigEntry = ConfigEntry[AlaskaCoordinator]


@dataclass(frozen=True, slots=True)
class HeaterState:
    """Decoded snapshot of registers 6..11 (6..13 for models with air controls)."""

    system_status: int
    feedback_status: int
    usage_hours: int
    vent24_remaining: int
    mode: int
    work_time_raw: int
    air_zone: int | None = None
    air_direction: int | None = None


def format_firmware(register: int) -> str:
    """Format the firmware register (hi byte major, lo byte minor): 0x020B -> 2.11."""
    return f"{register >> 8}.{register & 0xFF}"


# Gateway path unavailable / target failed to respond: a timeout in disguise
_GATEWAY_EXCEPTION_CODES = frozenset({0x0A, 0x0B})


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
        self.profile = get_profile(entry.data[CONF_MODEL])
        self.slave_id: int = entry.data[CONF_SLAVE_ID]
        self.work_time: int = DEFAULT_WORK_TIME
        self.firmware: str | None = None
        self.heater_type: int | None = None
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
            model=self.profile.device_model,
            sw_version=self.firmware,
        )

    async def async_read_device_info(self) -> None:
        """Read the firmware version (and heater type) once during setup.

        The verified 300BKP reads the identification block 0..5 in one request.
        Other models read single registers, because registers 3/4 may not exist
        on them; a device Modbus exception on such a read only leaves the value unknown
        (gateway exceptions 0x0A / 0x0B are timeouts and fail the setup).
        """
        profile = self.profile
        if profile.info_block_read:
            try:
                registers = await self.hub.async_read_holding_registers(
                    0, INFO_BLOCK_COUNT, self.slave_id
                )
            except AlaskaHubError as err:
                raise _translated_error(err, write=False) from err
            firmware: int | None = registers[profile.reg_firmware]
        else:
            firmware = await self._async_read_optional(profile.reg_firmware)
        if firmware is not None:
            self.firmware = format_firmware(firmware)
        if profile.has_heater_type:
            self.heater_type = await self._async_read_optional(REG_HEATER_TYPE)

    async def _async_read_optional(self, register: int) -> int | None:
        """Read one register; a device exception gives None, other errors raise."""
        try:
            return (
                await self.hub.async_read_holding_registers(register, 1, self.slave_id)
            )[0]
        except AlaskaHubError as err:
            if err.kind != "modbus" or err.code in _GATEWAY_EXCEPTION_CODES:
                raise _translated_error(err, write=False) from err
            _LOGGER.debug(
                "Register %s of %s (slave %s) not readable: %s",
                register,
                self.config_entry.title,
                self.slave_id,
                err,
            )
            return None

    async def _async_read_state(self) -> HeaterState:
        """Read the polled register block in a single request and decode it."""
        registers = await self.hub.async_read_holding_registers(
            POLL_START, self.profile.poll_count, self.slave_id
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
        """Write a work mode; models.plan_mode_write decides FC06 or FC16."""
        wanted = self.work_time if minutes is None else minutes
        plan = plan_mode_write(self.profile, mode, wanted)
        work_time_raw = 0
        if plan[0] == "fc06":
            await self._async_write(
                self.hub.async_write_register(REG_MODE, plan[1], self.slave_id), mode
            )
        else:
            work_time_raw = plan[1][1]
            await self._async_write(
                self.hub.async_write_registers(REG_MODE, plan[1], self.slave_id),
                mode,
            )
        if self.data is not None:
            # Show the new mode and its time fields immediately, not after the poll
            if mode == self.profile.mode_vent_24h:
                vent24, raw = VENT24_MINUTES, self.data.work_time_raw
            else:
                vent24, raw = 0, work_time_raw
            self.async_set_updated_data(
                replace(
                    self.data, mode=mode, vent24_remaining=vent24, work_time_raw=raw
                )
            )
        await self.async_request_refresh()

    async def async_stop(self) -> None:
        """Stop the heater."""
        await self.async_set_mode(self.profile.mode_off)

    async def async_set_work_time(self, minutes: int) -> None:
        """Store the work time; push it only if the device is running a timed mode.

        The decision uses a fresh read of the device, never the last polled
        state, so a stopped heater is not restarted by a stale mode value.
        """
        wanted = max(MIN_WORK_MINUTES, min(minutes, self.profile.max_work_minutes))
        async with self._write_lock:
            try:
                state = await self._async_read_state()
            except AlaskaHubError as err:
                raise _translated_error(err, write=False) from err
            self.async_set_updated_data(state)
            if state.mode in self.profile.mode_max_minutes:
                await self._async_set_mode(state.mode, wanted)
            self.work_time = wanted
        self.async_update_listeners()

    async def async_reset(self) -> None:
        """Reset the power board (only accepted by the device while stopped)."""
        await self._async_write_single(self.profile.reg_reset, RESET_MAGIC)
        await self.async_request_refresh()

    async def async_reset_filter(self) -> None:
        """Clear the "clean filter" message (300SRP)."""
        self._require(self.profile.has_filter_reset)
        await self._async_write_single(REG_USAGE_HOURS, RESET_MAGIC)
        await self.async_request_refresh()

    async def async_set_air_zone(self, value: int) -> None:
        """Set the air zone (300SRP; the device only accepts it while running)."""
        self._require(self.profile.has_air_controls)
        self._require(value in AIR_ZONES, value)
        await self._async_write_single(REG_AIR_ZONE, value)
        if self.data is not None:
            self.async_set_updated_data(replace(self.data, air_zone=value))
        await self.async_request_refresh()

    async def async_set_air_direction(self, value: int) -> None:
        """Set the air direction (300SRP; the device only accepts it while running)."""
        self._require(self.profile.has_air_controls)
        self._require(value in AIR_DIRECTIONS, value)
        await self._async_write_single(REG_AIR_DIRECTION, value)
        if self.data is not None:
            self.async_set_updated_data(replace(self.data, air_direction=value))
        await self.async_request_refresh()

    def _require(self, allowed: bool, value: int | None = None) -> None:
        """Refuse a write the model does not support or a value out of range."""
        if allowed:
            return
        if value is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unsupported_function",
                translation_placeholders={"model": self.profile.label},
            )
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_value",
            translation_placeholders={"value": str(value)},
        )

    async def _async_write_single(self, register: int, value: int) -> None:
        """Write one register with FC06 under the write lock."""
        async with self._write_lock:
            await self._async_write(
                self.hub.async_write_register(register, value, self.slave_id), None
            )

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
