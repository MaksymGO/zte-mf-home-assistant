"""Model/firmware registry. Add verified API variants here, not in entities."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FirmwareProfile:
    """Commands and authentication for one firmware family."""

    model: str
    version: str
    get_path: str = "/goform/goform_get_cmd_process"
    set_path: str = "/goform/goform_set_cmd_process"
    login_command: str = "LOGIN"
    password_encoding: str = "base64"
    commands: tuple[str, ...] = (
        "loginfo",
        "wa_inner_version",
        "hardware_version",
        "imei",
        "mac_address",
        "network_type",
        "network_provider",
        "signalbar",
        "ppp_status",
        "battery_vol_percent",
        "battery_charging",
        "simcard_roam",
        "pin_status",
        "rssi",
        "rscp",
        "lte_rsrp",
        "realtime_tx_bytes",
        "realtime_rx_bytes",
        "realtime_tx_thrpt",
        "realtime_rx_thrpt",
        "realtime_time",
    )


PROFILES = {
    "mf920u_b10": FirmwareProfile("MF920U", "BD_CNCNLMF920UV1.0.0B10"),
}
MODELS = tuple(sorted({profile.model for profile in PROFILES.values()}))


def select_profile(model: str, firmware: str, detected: str) -> FirmwareProfile:
    """Auto detection accepts only known versions; never guess a command set."""
    if firmware != "auto":
        profile = PROFILES.get(firmware)
        if profile is not None and profile.model == model:
            return profile
    else:
        for profile in PROFILES.values():
            if profile.model == model and profile.version == detected:
                return profile
    raise UnsupportedFirmware


class UnsupportedFirmware(Exception):
    """The selected model/firmware combination is not supported."""
