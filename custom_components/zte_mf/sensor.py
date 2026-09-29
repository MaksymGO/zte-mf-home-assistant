"""Modem telemetry sensors."""

import math
import re
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTime,
)

from .entity import ZteEntity


@dataclass(frozen=True, kw_only=True)
class ZteSensorDescription(SensorEntityDescription):
    """Add value conversion hints to the HA description."""

    numeric: bool = False
    minimum: float | None = None
    maximum: float | None = None


SENSORS = (
    ZteSensorDescription(key="network_type", name="Network type"),
    ZteSensorDescription(key="network_provider", name="Network operator"),
    ZteSensorDescription(key="pin_status", name="SIM status"),
    ZteSensorDescription(key="SSID1", translation_key="network_name", icon="mdi:wifi"),
    ZteSensorDescription(
        key="wifi_connected_devices_count",
        translation_key="wifi_connected_devices",
        numeric=True,
        minimum=0,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:account-multiple",
    ),
    ZteSensorDescription(
        key="battery_vol_percent",
        name="Battery",
        numeric=True,
        minimum=0,
        maximum=100,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    *(
        ZteSensorDescription(
            key=key,
            name=name,
            numeric=True,
            minimum=0,
            device_class=SensorDeviceClass.DATA_SIZE,
            native_unit_of_measurement=UnitOfInformation.BYTES,
            state_class=SensorStateClass.TOTAL_INCREASING,
        )
        for key, name in (
            ("realtime_rx_bytes", "Session received"),
            ("realtime_tx_bytes", "Session sent"),
        )
    ),
    *(
        ZteSensorDescription(
            key=key,
            name=name,
            numeric=True,
            minimum=0,
            device_class=SensorDeviceClass.DATA_RATE,
            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
            state_class=SensorStateClass.MEASUREMENT,
        )
        for key, name in (
            ("realtime_rx_thrpt", "Download speed"),
            ("realtime_tx_thrpt", "Upload speed"),
        )
    ),
    ZteSensorDescription(
        key="realtime_time",
        name="Connection duration",
        numeric=True,
        minimum=0,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


def sensor_value(raw, description):
    """Treat absent, malformed and sentinel readings as unknown, never zero."""
    if raw is None or str(raw).strip() in ("", "--", "N/A"):
        return None
    if not description.numeric:
        return str(raw)
    value = str(raw).strip()
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?(?:\s*dBm)?", value):
        return None
    number = float(value.removesuffix("dBm").strip())
    if (
        not math.isfinite(number)
        or (description.minimum is not None and number < description.minimum)
        or (description.maximum is not None and number > description.maximum)
    ):
        return None
    return number


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(ZteSensor(entry.runtime_data, entry, item) for item in SENSORS)


class ZteSensor(ZteEntity, SensorEntity):
    """A sensor updated by the shared coordinator."""

    def __init__(self, coordinator, entry, description):
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return sensor_value(
            self.coordinator.data.get(self.entity_description.key), self.entity_description
        )
