"""Common device information."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MODEL, DOMAIN
from .coordinator import ZteCoordinator


class ZteEntity(CoordinatorEntity[ZteCoordinator]):
    """An entity belonging to a modem, with a stable hardware-derived ID."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            manufacturer="ZTE",
            model=entry.data[CONF_MODEL],
            name=entry.title,
            sw_version=coordinator.data.get("wa_inner_version") or None,
            hw_version=coordinator.data.get("hardware_version") or None,
            configuration_url=coordinator.client.base_url,
        )
