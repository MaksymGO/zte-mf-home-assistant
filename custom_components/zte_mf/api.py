"""Asynchronous Goform telemetry and control client."""

import asyncio
import base64
import ipaddress
import re
from urllib.parse import urlsplit

import aiohttp

from .profiles import FirmwareProfile, select_profile


class CannotConnect(Exception):
    """The modem did not return a usable response."""


class InvalidAuth(Exception):
    """The modem requires valid credentials."""


def normalize_host(value: str) -> str:
    """Accept a hostname/IP and optional port, without credentials or paths."""
    value = value.strip()
    parsed = urlsplit(value if "://" in value else f"http://{value}")
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid modem address")
    hostname = parsed.hostname.lower()
    try:
        address = ipaddress.ip_address(hostname)
        hostname = f"[{address}]" if address.version == 6 else str(address)
    except ValueError:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", hostname):
            raise ValueError("Invalid hostname") from None
    port = parsed.port
    suffix = f":{port}" if port and port != (443 if parsed.scheme == "https" else 80) else ""
    return f"{parsed.scheme}://{hostname}{suffix}"


class ZteClient:
    """Each instance requires a private session/cookie jar, including IP cookies."""

    def __init__(
        self, session: aiohttp.ClientSession, host: str, password: str, model: str, firmware: str
    ) -> None:
        self.session = session
        self.base_url = normalize_host(host)
        self.password = password
        self.model = model
        self.firmware = firmware
        self.profile: FirmwareProfile | None = None
        self._lock = asyncio.Lock()

    async def _request(self, method: str, path: str, data: dict) -> dict:
        kwargs = {"params" if method == "GET" else "data": data}
        try:
            async with self.session.request(
                method,
                self.base_url + path,
                **kwargs,
                headers={"Referer": self.base_url + "/index.html", "Origin": self.base_url},
                timeout=aiohttp.ClientTimeout(total=10),
                allow_redirects=False,
            ) as response:
                if response.status in (401, 403):
                    raise InvalidAuth
                if response.status != 200:
                    raise CannotConnect
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise CannotConnect from err
        if not isinstance(payload, dict):
            raise CannotConnect
        return payload

    async def _get(self, commands: tuple[str, ...]) -> dict:
        path = self.profile.get_path if self.profile else "/goform/goform_get_cmd_process"
        return await self._request(
            "GET",
            path,
            {
                "isTest": "false",
                "cmd": ",".join(commands),
                "multi_data": "1",
            },
        )

    async def _login(self) -> None:
        if not self.password:
            raise InvalidAuth
        assert self.profile is not None
        if self.profile.password_encoding != "base64":
            raise CannotConnect
        result = await self._request(
            "POST",
            self.profile.set_path,
            {
                "isTest": "false",
                "goformId": self.profile.login_command,
                "password": base64.b64encode(self.password.encode()).decode("ascii"),
            },
        )
        if str(result.get("result")) not in ("0", "4"):
            raise InvalidAuth

    async def async_update(self) -> dict:
        """Recover one expired session; never repeatedly retry bad credentials."""
        async with self._lock:
            if self.profile is None:
                info = await self._get(("wa_inner_version",))
                version = info.get("wa_inner_version")
                if not isinstance(version, str) or not version:
                    raise CannotConnect
                self.profile = select_profile(self.model, self.firmware, version)
            logged_in = False
            try:
                status = await self._get(("loginfo",))
            except InvalidAuth:
                status = {}
            if status.get("loginfo") != "ok":
                await self._login()
                logged_in = True
            try:
                data = await self._get(self.profile.commands)
            except InvalidAuth:
                data = {}
            if data.get("loginfo") != "ok":
                if logged_in:
                    raise InvalidAuth
                await self._login()
                data = await self._get(self.profile.commands)
                if data.get("loginfo") != "ok":
                    raise InvalidAuth
            if not any(
                data.get(key)
                for key in ("ppp_status", "network_type", "pin_status", "battery_vol_percent")
            ):
                raise CannotConnect
            return data

    async def async_shutdown(self) -> None:
        """Request the same shutdown action as the modem's web interface."""
        async with self._lock:
            try:
                status = await self._get(("loginfo",))
            except InvalidAuth:
                status = {}
            if status.get("loginfo") != "ok":
                await self._login()
            assert self.profile is not None
            await self._request(
                "POST",
                self.profile.set_path,
                {"isTest": "false", "goformId": self.profile.shutdown_command},
            )


def device_id(data: dict) -> str | None:
    """Use modem hardware identity, never the SIM identity or IP address."""
    imei = data.get("imei", "")
    if isinstance(imei, str) and re.fullmatch(r"\d{15}", imei) and set(imei) != {"0"}:
        return imei
    mac = str(data.get("mac_address", "")).replace(":", "").replace("-", "").lower()
    if re.fullmatch(r"[0-9a-f]{12}", mac) and mac != "000000000000":
        return mac
    return None
