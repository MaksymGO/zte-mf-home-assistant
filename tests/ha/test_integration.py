"""Run config flows, real entity setup, options, reauth and unload in HA."""

from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zte_mf.api import CannotConnect, InvalidAuth
from custom_components.zte_mf.const import DOMAIN
from custom_components.zte_mf.profiles import UnsupportedFirmware

DATA = {
    "host": "http://192.168.0.1",
    "password": "test-password",
    "model": "MF920U",
    "firmware": "auto",
}


async def test_setup_and_unload(hass, update):
    entry = MockConfigEntry(
        domain=DOMAIN, data=DATA, unique_id="123456789012345", title="ZTE MF920U"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.zte_mf920u_battery").state == "75.0"
    assert hass.states.get("binary_sensor.zte_mf920u_mobile_connection").state == "on"
    session = entry.runtime_data.client.session
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert session.closed


async def test_user_and_duplicate(hass, update):
    with patch("custom_components.zte_mf.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DATA
        )
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "exception,error",
    [
        (CannotConnect, "cannot_connect"),
        (InvalidAuth, "invalid_auth"),
        (UnsupportedFirmware, "unsupported_firmware"),
    ],
)
async def test_flow_errors(hass, update, exception, error):
    update.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=DATA
    )
    assert result["errors"] == {"base": error}


async def test_missing_identity(hass, update):
    update.return_value = {"ppp_status": "ppp_connected"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=DATA
    )
    assert result["errors"]["base"] == "missing_identity"


async def test_reconfigure_wrong_device(hass, update):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="999999999999999")
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}, data=DATA
    )
    assert result["reason"] == "wrong_device"


async def test_reauth(hass, update):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="123456789012345")
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": entry.entry_id}, data=DATA
    )
    with patch("homeassistant.config_entries.ConfigEntries.async_reload", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**DATA, "password": "new-password"}
        )
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new-password"


async def test_options(hass, update):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="123456789012345")
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["scan_interval"] == 60


def test_missing_and_invalid_sensor_values():
    from custom_components.zte_mf.sensor import SENSORS, sensor_value

    battery = next(item for item in SENSORS if item.key == "battery_vol_percent")
    assert not {"imei", "imsi", "wan_ipaddr", "rssi", "rscp", "lte_rsrp"} & {
        item.key for item in SENSORS
    }
    for value in (None, "", "--", "N/A", "nan", "999", "-1"):
        assert sensor_value(value, battery) is None
    assert sensor_value("0", battery) == 0


async def test_connection_loss_and_recovery(hass, update, modem_data):
    entry = MockConfigEntry(
        domain=DOMAIN, data=DATA, unique_id="123456789012345", title="ZTE MF920U"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    update.side_effect = CannotConnect
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.zte_mf920u_battery").state == "unavailable"
    update.side_effect = None
    update.return_value = modem_data
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.zte_mf920u_battery").state == "75.0"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_wrong_modem_during_poll(hass, update, modem_data):
    entry = MockConfigEntry(
        domain=DOMAIN, data=DATA, unique_id="123456789012345", title="ZTE MF920U"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    update.return_value = {**modem_data, "imei": "999999999999999"}
    await entry.runtime_data.async_refresh()
    assert not entry.runtime_data.last_update_success
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "error,state",
    [
        (CannotConnect, ConfigEntryState.SETUP_RETRY),
        (InvalidAuth, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_failed_setup_releases_session(hass, update, error, state):
    from custom_components.zte_mf.coordinator import create_client

    client = create_client(hass, DATA)
    update.side_effect = error
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="123456789012345")
    entry.add_to_hass(hass)
    with patch("custom_components.zte_mf.coordinator.create_client", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is state
    assert client.session.closed


async def test_reconfigure_keeps_password(hass, update):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="123456789012345")
    entry.add_to_hass(hass)
    with patch("homeassistant.config_entries.ConfigEntries.async_reload", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
            data={**DATA, "host": "192.168.0.2", "password": ""},
        )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["host"] == "http://192.168.0.2"
    assert entry.data["password"] == "test-password"


@pytest.mark.parametrize(
    "radio_off,expected",
    [("0", False), ("1", True), ("2", None), ("", None), (None, None)],
)
def test_wifi_switch_reports_firmware_state(radio_off, expected):
    from types import SimpleNamespace

    from custom_components.zte_mf.switch import SWITCHES, ZteSwitch

    switch = object.__new__(ZteSwitch)
    switch.coordinator = SimpleNamespace(data={"RadioOff": radio_off})
    switch.entity_description = SWITCHES[0]
    switch._data_key = "RadioOff"
    assert switch.is_on is expected
