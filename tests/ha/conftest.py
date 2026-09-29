"""Home Assistant integration fixtures (Linux)."""

from unittest.mock import AsyncMock, patch

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def custom_integration(enable_custom_integrations):
    yield


@pytest.fixture
def modem_data():
    return {
        "loginfo": "ok",
        "imei": "123456789012345",
        "ppp_status": "ppp_connected",
        "wa_inner_version": "BD_CNCNLMF920UV1.0.0B10",
        "battery_vol_percent": "75",
        "battery_charging": "1",
        "lte_rsrp": "-95",
        "network_type": "LTE",
    }


@pytest.fixture
def update(modem_data):
    with patch(
        "custom_components.zte_mf.api.ZteClient.async_update",
        new_callable=AsyncMock,
        return_value=modem_data,
    ) as mocked:
        yield mocked
