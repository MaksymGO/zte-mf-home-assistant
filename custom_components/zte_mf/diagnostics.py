"""Downloadable modem diagnostics with credentials and personal identifiers redacted."""

from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from . import ZteConfigEntry

TO_REDACT = {CONF_HOST, CONF_PASSWORD, "imei", "imsi", "wan_ipaddr", "SSID1"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ZteConfigEntry) -> dict:
    """Expose requested radio and network details in downloaded diagnostics."""
    data = entry.runtime_data.data
    return async_redact_data(
        {
            "config": dict(entry.data),
            "modem": {
                "model": entry.data["model"],
                "firmware_profile": entry.data["firmware"],
                "hardware_version": data.get("hardware_version"),
                "firmware_version": data.get("wa_inner_version"),
                "identifiers": {
                    "imei": data.get("imei"),
                    "imsi": data.get("imsi"),
                },
                "signal": {
                    "signalbar": data.get("signalbar"),
                    "rssi": data.get("rssi"),
                    "rscp": data.get("rscp"),
                    "lte_rsrp": data.get("lte_rsrp"),
                },
                "network": {
                    "network_type": data.get("network_type"),
                    "network_provider": data.get("network_provider"),
                    "wan_ipaddr": data.get("wan_ipaddr"),
                    "ppp_status": data.get("ppp_status"),
                    "modem_main_state": data.get("modem_main_state"),
                },
                "wifi": {
                    "SSID1": data.get("SSID1"),
                    "RadioOff": data.get("RadioOff"),
                    "connected_devices": data.get("wifi_connected_devices_count"),
                },
                "mobile_data": {"switch_state": data.get("ppp_status")},
            },
        },
        TO_REDACT,
    )
