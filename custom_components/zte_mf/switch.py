"""Controllable Wi-Fi and LTE switches."""

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

from .entity import ZteEntity

SWITCHES = (
    SwitchEntityDescription(key="wifi_switch", translation_key="wifi_switch", icon="mdi:wifi"),
    SwitchEntityDescription(
        key="lte_switch", translation_key="lte_switch", icon="mdi:signal-cellular-3"
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up controllable modem switches."""
    async_add_entities(ZteSwitch(entry.runtime_data, entry, description) for description in SWITCHES)


class ZteSwitch(ZteEntity, SwitchEntity):
    """Control a modem radio or its mobile-data connection."""

    def __init__(self, coordinator, entry, description):
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description
        self._data_key = "RadioOff" if description.key == "wifi_switch" else "ppp_status"

    @property
    def is_on(self):
        value = self.coordinator.data.get(self._data_key)
        if self.entity_description.key == "wifi_switch":
            return {"0": True, "1": False}.get(value)
        return {
            "ppp_connected": True,
            "ppp_connecting": True,
            "ppp_disconnected": False,
            "ppp_disconnecting": False,
        }.get(value)

    async def async_turn_on(self, **kwargs):
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs):
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool):
        """Send the device command and publish the acknowledged state."""
        if self.entity_description.key == "wifi_switch":
            await self.coordinator.client.async_set_wifi(enabled)
            state = {**self.coordinator.data, "RadioOff": "0" if enabled else "1"}
        else:
            status = await self.coordinator.client.async_set_lte(enabled)
            state = {**self.coordinator.data, **status}
        self.coordinator.async_set_updated_data(state)
