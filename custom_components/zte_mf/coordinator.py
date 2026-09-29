"""Shared polling and session ownership."""

import logging
from datetime import timedelta

from aiohttp import CookieJar
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, InvalidAuth, ZteClient, device_id
from .const import CONF_FIRMWARE, CONF_MODEL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .profiles import UnsupportedFirmware

_LOGGER = logging.getLogger(__name__)


def create_client(hass: HomeAssistant, data: dict, *, auto_cleanup: bool = False) -> ZteClient:
    """Own the session: modem cookies must not leak between config entries."""
    session = async_create_clientsession(
        hass, auto_cleanup=auto_cleanup, cookie_jar=CookieJar(unsafe=True)
    )
    return ZteClient(
        session, data[CONF_HOST], data[CONF_PASSWORD], data[CONF_MODEL], data[CONF_FIRMWARE]
    )


class ZteCoordinator(DataUpdateCoordinator[dict]):
    """Poll all entities in one modem request."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
            always_update=False,
        )
        self.client = create_client(hass, dict(entry.data), auto_cleanup=True)
        self.expected_id = entry.unique_id

    async def _async_update_data(self) -> dict:
        try:
            data = await self.client.async_update()
            if device_id(data) != self.expected_id:
                raise UpdateFailed("Modem identity changed or is missing")
            return data
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except UnsupportedFirmware as err:
            raise ConfigEntryError("Unsupported modem firmware") from err
        except CannotConnect as err:
            raise UpdateFailed("Cannot read modem status") from err
