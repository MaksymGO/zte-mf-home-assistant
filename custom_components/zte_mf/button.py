"""Control buttons for ZTE MF modems."""

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription

from .entity import ZteEntity

SHUTDOWN = ButtonEntityDescription(
    key="shutdown",
    translation_key="shutdown",
    icon="mdi:power",
)
REBOOT = ButtonEntityDescription(
    key="reboot",
    translation_key="reboot",
    icon="mdi:restart",
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up modem control buttons."""
    async_add_entities(
        [
            ZteShutdownButton(entry.runtime_data, entry),
            ZteRebootButton(entry.runtime_data, entry),
        ]
    )


class ZteShutdownButton(ZteEntity, ButtonEntity):
    """Power off the modem through its web-interface Goform command."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, SHUTDOWN.key)
        self.entity_description = SHUTDOWN

    async def async_press(self) -> None:
        """Send the modem's SHUTDOWN_DEVICE command."""
        await self.coordinator.client.async_shutdown()


class ZteRebootButton(ZteEntity, ButtonEntity):
    """Restart the modem through its web-interface Goform command."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, REBOOT.key)
        self.entity_description = REBOOT

    async def async_press(self) -> None:
        """Send the modem's REBOOT_DEVICE command."""
        await self.coordinator.client.async_reboot()
