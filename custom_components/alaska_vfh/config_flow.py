"""Config flow for Alaska Bath Heater (Modbus)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    REG_DEVICE_ID,
)
from .hub import AlaskaHubError, async_acquire_hub, async_release_hub
from .models import DEFAULT_MODEL, INFO_BLOCK_COUNT, PROFILES, get_profile


class AlaskaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Three-step flow (gateway, heater model, heater) plus a reconfigure step."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the flow."""
        self._host = ""
        self._port = DEFAULT_PORT
        self._model = DEFAULT_MODEL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AlaskaOptionsFlow:
        """Return the options flow."""
        return AlaskaOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the gateway and check that it accepts TCP connections."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip().lower()
            port = int(user_input[CONF_PORT])
            if not host or not 1 <= port <= 65535:
                errors["base"] = "cannot_connect"
            else:
                hub = async_acquire_hub(self.hass, host, port)
                try:
                    await hub.async_connect()
                except AlaskaHubError:
                    errors["base"] = "cannot_connect"
                finally:
                    async_release_hub(self.hass, hub)
            if not errors:
                self._host = host
                self._port = port
                return await self.async_step_model()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=(user_input or {}).get(CONF_PORT, DEFAULT_PORT),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which heater model is connected."""
        if user_input is not None:
            self._model = user_input[CONF_MODEL]
            return await self.async_step_device()
        return self.async_show_form(
            step_id="model",
            data_schema=vol.Schema(
                {vol.Required(CONF_MODEL, default=self._model): _model_selector()}
            ),
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the heater name and slave id, then verify the device answers."""
        errors: dict[str, str] = {}
        if user_input is not None:
            slave_id = int(user_input[CONF_SLAVE_ID])
            if not 1 <= slave_id <= 255:
                errors[CONF_SLAVE_ID] = "invalid_slave"
            else:
                await self.async_set_unique_id(f"{self._host}:{self._port}:{slave_id}")
                self._abort_if_unique_id_configured()
                error = await _async_validate(
                    self.hass, self._host, self._port, slave_id, self._model
                )
                if error is None:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data={
                            CONF_HOST: self._host,
                            CONF_PORT: self._port,
                            CONF_SLAVE_ID: slave_id,
                            CONF_MODEL: self._model,
                        },
                    )
                errors[CONF_SLAVE_ID if error == "invalid_slave" else "base"] = error
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=(user_input or {}).get(
                            CONF_NAME, get_profile(self._model).default_name
                        ),
                    ): str,
                    vol.Required(
                        CONF_SLAVE_ID, default=(user_input or {}).get(CONF_SLAVE_ID, 1)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=255, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host, port, device id and model of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip().lower()
            port = int(user_input[CONF_PORT])
            slave_id = int(user_input[CONF_SLAVE_ID])
            model = user_input[CONF_MODEL]
            unique_id = f"{host}:{port}:{slave_id}"
            other = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, unique_id
            )
            if other is not None and other.entry_id != entry.entry_id:
                return self.async_abort(reason="already_configured")
            if not host or not 1 <= port <= 65535:
                errors["base"] = "cannot_connect"
            elif not 1 <= slave_id <= 255:
                errors[CONF_SLAVE_ID] = "invalid_slave"
            else:
                error = await _async_validate(self.hass, host, port, slave_id, model)
                if error is None:
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=unique_id,
                        data_updates={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_SLAVE_ID: slave_id,
                            CONF_MODEL: model,
                        },
                    )
                errors[CONF_SLAVE_ID if error == "invalid_slave" else "base"] = error
        current = {**entry.data, **(user_input or {})}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current[CONF_HOST]): str,
                    vol.Required(CONF_PORT, default=current[CONF_PORT]): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_SLAVE_ID, default=current[CONF_SLAVE_ID]
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=255, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_MODEL, default=current[CONF_MODEL]
                    ): _model_selector(),
                }
            ),
            errors=errors,
        )


def _model_selector() -> SelectSelector:
    """Dropdown of the supported heater models."""
    return SelectSelector(
        SelectSelectorConfig(
            options=list(PROFILES),
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="model",
        )
    )


async def _async_validate(
    hass: HomeAssistant, host: str, port: int, slave_id: int, model: str
) -> str | None:
    """Read the device id; return an error key or None when the device answers.

    The verified 300BKP reads registers 0..5 in one request; other models read
    register 0 only, because register 3 may not exist on them.
    """
    count = INFO_BLOCK_COUNT if get_profile(model).info_block_read else 1
    hub = async_acquire_hub(hass, host, port)
    try:
        registers = await hub.async_read_holding_registers(0, count, slave_id)
    except AlaskaHubError as err:
        return "cannot_connect" if err.kind == "connect" else "no_response"
    finally:
        async_release_hub(hass, hub)
    if registers[REG_DEVICE_ID] != slave_id:
        return "invalid_slave"
    return None


class AlaskaOptionsFlow(OptionsFlowWithReload):
    """Options: polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the polling interval."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                    )
                }
            ),
        )
