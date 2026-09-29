"""Connectivity, charging and roaming state."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .entity import ZteEntity

SENSORS = (
    BinarySensorEntityDescription(
        key="ppp_status",
        name="Mobile connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="battery_charging",
        name="Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    BinarySensorEntityDescription(key="simcard_roam", name="Roaming", icon="mdi:earth"),
    BinarySensorEntityDescription(
        key="roam_setting_option",
        translation_key="roaming_allowed",
        icon="mdi:earth",
    ),
)
STATES = {
    "ppp_status": {"ppp_connected": True, "ppp_disconnected": False},
    "battery_charging": {"1": True, "0": False},
    "simcard_roam": {"R": True, "N": False},
    "roam_setting_option": {"on": True, "off": False},
}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(ZteBinarySensor(entry.runtime_data, entry, item) for item in SENSORS)


class ZteBinarySensor(ZteEntity, BinarySensorEntity):
    """Preserve unknown states when firmware does not supply a value."""

    def __init__(self, coordinator, entry, description):
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def is_on(self):
        key = self.entity_description.key
        return STATES[key].get(self.coordinator.data.get(key))
