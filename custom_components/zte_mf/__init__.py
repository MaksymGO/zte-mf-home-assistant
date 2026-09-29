"""Home Assistant integration for ZTE MF modems."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import ZteCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SWITCH]
type ZteConfigEntry = ConfigEntry[ZteCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ZteConfigEntry) -> bool:
    """Create the modem session and forward platforms after the first poll."""
    coordinator = ZteCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        coordinator.client.session.detach()
        raise
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZteConfigEntry) -> bool:
    """Close the private cookie session after unloading entities."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.client.session.detach()
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ZteConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
