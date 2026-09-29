"""UI setup, reconfiguration, reauthentication and polling options."""

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import CannotConnect, InvalidAuth, device_id, normalize_host
from .const import CONF_FIRMWARE, CONF_MODEL, DEFAULT_HOST, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import create_client
from .profiles import MODELS, PROFILES, UnsupportedFirmware


class ZteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure one modem with a verified firmware profile."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ZteOptionsFlow()

    async def async_step_user(self, user_input=None):
        return await self._configure(user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._configure(user_input)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._configure(user_input)

    async def _configure(self, user_input):
        entry = None
        step = "user"
        if self.source == "reconfigure":
            entry = self._get_reconfigure_entry()
            step = "reconfigure"
        elif self.source == "reauth":
            entry = self._get_reauth_entry()
            step = "reauth_confirm"
        defaults = dict(entry.data) if entry else {}
        errors = {}
        if user_input is not None:
            data = dict(user_input)
            # A blank password during reconfiguration retains the stored secret.
            data[CONF_PASSWORD] = data.get(CONF_PASSWORD) or defaults.get(CONF_PASSWORD, "")
            defaults.update({key: value for key, value in data.items() if key != CONF_PASSWORD})
            client = None
            try:
                data[CONF_HOST] = normalize_host(data[CONF_HOST])
                if data[CONF_MODEL] not in MODELS or (
                    data[CONF_FIRMWARE] != "auto"
                    and (
                        data[CONF_FIRMWARE] not in PROFILES
                        or PROFILES[data[CONF_FIRMWARE]].model != data[CONF_MODEL]
                    )
                ):
                    raise UnsupportedFirmware
                client = create_client(self.hass, data)
                status = await client.async_update()
                unique_id = device_id(status)
                if not unique_id:
                    errors["base"] = "missing_identity"
                elif entry:
                    if unique_id != entry.unique_id:
                        return self.async_abort(reason="wrong_device")
                    return self.async_update_reload_and_abort(entry, data_updates=data)
                else:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=f"ZTE {data[CONF_MODEL]}", data=data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except UnsupportedFirmware:
                errors["base"] = "unsupported_firmware"
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            finally:
                if client is not None:
                    client.session.detach()
        firmware_options = [{"value": "auto", "label": "Automatic"}] + [
            {"value": key, "label": f"{profile.model} — {profile.version}"}
            for key, profile in PROFILES.items()
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST)): str,
                vol.Required(
                    CONF_MODEL, default=defaults.get(CONF_MODEL, "MF920U")
                ): selector.SelectSelector(selector.SelectSelectorConfig(options=list(MODELS))),
                vol.Required(
                    CONF_FIRMWARE, default=defaults.get(CONF_FIRMWARE, "auto")
                ): selector.SelectSelector(selector.SelectSelectorConfig(options=firmware_options)),
                vol.Optional(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(step_id=step, data_schema=schema, errors=errors)


class ZteOptionsFlow(OptionsFlow):
    """Change the polling interval without re-entering credentials."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                }
            ),
        )
