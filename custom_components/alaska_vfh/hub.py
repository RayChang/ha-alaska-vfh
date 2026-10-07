"""Shared Modbus TCP gateway connection for Alaska VFH."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Literal

from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException
from pymodbus.pdu import ModbusPDU

from .const import (
    DEFAULT_REQUEST_GAP,
    DOMAIN,
    REQUEST_RETRIES,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

type HubKey = tuple[str, int]
type ErrorKind = Literal["connect", "timeout", "modbus"]

HUBS: HassKey[dict[HubKey, AlaskaHub]] = HassKey(DOMAIN)


class AlaskaHubError(Exception):
    """A request to the gateway or device failed."""

    def __init__(self, kind: ErrorKind, message: str, code: int | None = None) -> None:
        """Store the failure kind and, for Modbus exceptions, the exception code."""
        super().__init__(message)
        self.kind: ErrorKind = kind
        self.code: int | None = code


class AlaskaHub:
    """One Modbus TCP client for a (host, port) gateway, shared by all entries."""

    def __init__(
        self, host: str, port: int, request_gap: float = DEFAULT_REQUEST_GAP
    ) -> None:
        """Create the hub; the TCP connection is opened lazily."""
        self.host = host
        self.port = port
        self._gap = request_gap
        self._client = AsyncModbusTcpClient(
            host,
            port=port,
            timeout=REQUEST_TIMEOUT,
            retries=REQUEST_RETRIES,
            reconnect_delay=0,  # the hub owns reconnecting; no background task
        )
        self._lock = asyncio.Lock()
        self._last_request = 0.0
        self._refs = 0

    async def async_connect(self) -> None:
        """Make sure the TCP connection to the gateway is open."""
        async with self._lock:
            await self._async_ensure_connected()

    async def async_read_holding_registers(
        self, address: int, count: int, slave: int
    ) -> list[int]:
        """Read holding registers (FC03)."""
        response = await self._async_request(
            lambda: self._client.read_holding_registers(
                address, count=count, device_id=slave
            )
        )
        registers = list(response.registers)
        if len(registers) != count:
            raise AlaskaHubError(
                "connect",
                f"Short reply from device: expected {count} registers, "
                f"got {len(registers)}",
            )
        return registers

    async def async_write_register(self, address: int, value: int, slave: int) -> None:
        """Write a single holding register (FC06)."""
        await self._async_request(
            lambda: self._client.write_register(address, value, device_id=slave)
        )

    async def async_write_registers(
        self, address: int, values: list[int], slave: int
    ) -> None:
        """Write several consecutive holding registers (FC16)."""
        await self._async_request(
            lambda: self._client.write_registers(address, values, device_id=slave)
        )

    def acquire(self) -> None:
        """Take a reference to this hub."""
        self._refs += 1

    def release(self) -> bool:
        """Drop one reference; close the connection when none is left."""
        self._refs -= 1
        if self._refs > 0:
            return False
        self._client.close()
        return True

    async def _async_ensure_connected(self) -> None:
        """Open the TCP connection if it is not connected (caller holds the lock)."""
        if self._client.connected:
            return
        self._client.close()  # drop any half-open transport before reconnecting
        try:
            connected = await self._client.connect()
        except (OSError, ModbusException) as err:
            raise AlaskaHubError(
                "connect", f"Cannot connect to {self.host}:{self.port}: {err}"
            ) from err
        if not connected:
            raise AlaskaHubError(
                "connect", f"Cannot connect to {self.host}:{self.port}"
            )

    async def _async_request(
        self, request: Callable[[], Awaitable[ModbusPDU]]
    ) -> ModbusPDU:
        """Run one serialised request, honouring the inter-request gap."""
        loop = asyncio.get_running_loop()
        async with self._lock:
            await self._async_ensure_connected()
            wait = self._gap - (loop.time() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                response = await request()
            except ConnectionException as err:
                self._client.close()
                raise AlaskaHubError("connect", f"Connection lost: {err}") from err
            except (ModbusIOException, TimeoutError) as err:
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    # pymodbus maps CancelledError to ModbusIOException; restore it
                    raise asyncio.CancelledError from err
                raise AlaskaHubError("timeout", f"No response: {err}") from err
            except (OSError, ModbusException) as err:
                self._client.close()
                raise AlaskaHubError("connect", f"Communication error: {err}") from err
            finally:
                self._last_request = loop.time()
        if response.isError():
            code = getattr(response, "exception_code", None)
            _LOGGER.debug("Modbus exception %s from %s:%s", code, self.host, self.port)
            raise AlaskaHubError(
                "modbus", f"Modbus exception {code}", code if code is not None else -1
            )
        return response


def async_acquire_hub(hass: HomeAssistant, host: str, port: int) -> AlaskaHub:
    """Return the shared hub for a gateway, creating it for the first user."""
    hubs = hass.data.setdefault(HUBS, {})
    key = (host, port)
    hub = hubs.get(key)
    if hub is None:
        hub = hubs[key] = AlaskaHub(host, port)
    hub.acquire()
    return hub


def async_release_hub(hass: HomeAssistant, hub: AlaskaHub) -> None:
    """Release a hub reference; the last release closes the gateway connection."""
    if hub.release():
        hass.data.get(HUBS, {}).pop((hub.host, hub.port), None)
