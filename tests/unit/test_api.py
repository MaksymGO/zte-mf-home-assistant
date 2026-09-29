"""Exercise real HTTP, cookies, login recovery and malformed modem responses."""

import base64

import pytest
from aiohttp import ClientSession, CookieJar, web
from zte_transport.api import CannotConnect, InvalidAuth, ZteClient, device_id, normalize_host
from zte_transport.profiles import PROFILES, UnsupportedFirmware, select_profile

VERSION = "BD_CNCNLMF920UV1.0.0B10"


@pytest.fixture
async def modem():
    state = {
        "posts": [],
        "expired": False,
        "bad_auth": False,
        "bad_json": False,
        "missing_status": False,
        "http_error": False,
        "ppp_status": "ppp_connected",
        "radio_off": "1",
        "m_ssid_enable": "0",
    }

    async def get(request):
        if state["http_error"]:
            return web.Response(status=503)
        if state["bad_json"]:
            return web.Response(text="<html>error</html>")
        commands = request.query["cmd"]
        if commands == "wa_inner_version":
            return web.json_response({"wa_inner_version": VERSION})
        if commands == "wa_inner_version,cr_version":
            return web.json_response({"wa_inner_version": VERSION, "cr_version": ""})
        if commands == "RD":
            return web.json_response({"RD": "random-data"})
        if commands == "RadioOff":
            return web.json_response({"RadioOff": state["radio_off"]})
        if commands == "m_ssid_enable":
            return web.json_response({"m_ssid_enable": state["m_ssid_enable"]})
        logged_in = request.cookies.get("stok") == "test-session"
        if state["expired"] and "," in commands:
            state["expired"] = False
            return web.json_response({"loginfo": ""})
        if commands == "loginfo" or not logged_in:
            return web.json_response({"loginfo": "ok" if logged_in else ""})
        if state["missing_status"]:
            return web.json_response({"loginfo": "ok"})
        return web.json_response(
            {
                "loginfo": "ok",
                "wa_inner_version": VERSION,
                "imei": "123456789012345",
                "ppp_status": state["ppp_status"],
                "battery_vol_percent": "75",
            }
        )

    async def post(request):
        data = dict(await request.post())
        state["posts"].append(data)
        assert request.headers["Referer"].endswith("/index.html")
        if data["goformId"] == "LOGIN" and state["bad_auth"]:
            return web.json_response({"result": "3"})
        result = web.json_response({"result": "0"})
        result.set_cookie("stok", "test-session")
        if data["goformId"] == "DISCONNECT_NETWORK":
            state["ppp_status"] = "ppp_disconnected"
            result = web.json_response({"result": "success"})
        elif data["goformId"] == "CONNECT_NETWORK":
            state["ppp_status"] = "ppp_connected"
            result = web.json_response({"result": "success"})
        elif data["goformId"] == "SET_WIFI_INFO":
            state["radio_off"] = "0" if data["wifiEnabled"] == "1" else "1"
            result = web.json_response({"result": "success"})
        result.set_cookie("stok", "test-session")
        return result

    app = web.Application()
    app.router.add_get("/goform/goform_get_cmd_process", get)
    app.router.add_post("/goform/goform_set_cmd_process", post)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    async with ClientSession(cookie_jar=CookieJar(unsafe=True)) as session:
        client = ZteClient(session, f"127.0.0.1:{port}", "test-password", "MF920U", "auto")
        yield client, state
    await runner.cleanup()


async def test_login_cookie_reuse_and_expiry(modem):
    client, state = modem
    assert (await client.async_update())["battery_vol_percent"] == "75"
    assert state["posts"][0]["password"] == base64.b64encode(b"test-password").decode()
    await client.async_update()
    assert len(state["posts"]) == 1
    state["expired"] = True
    await client.async_update()
    assert len(state["posts"]) == 2


@pytest.mark.parametrize(
    "enabled,command,status",
    [(True, "CONNECT_NETWORK", "ppp_connected"), (False, "DISCONNECT_NETWORK", "ppp_disconnected")],
)
async def test_lte_switch_uses_firmware_ad(modem, enabled, command, status):
    import hashlib

    client, state = modem
    await client.async_update()
    assert (await client.async_set_lte(enabled))["ppp_status"] == status
    post = next(item for item in state["posts"] if item["goformId"] != "LOGIN")
    inner_hash = hashlib.md5(VERSION.encode()).hexdigest()
    expected_ad = hashlib.md5(f"{inner_hash}random-data".encode()).hexdigest()
    assert post == {
        "isTest": "false",
        "notCallback": "true",
        "goformId": command,
        "AD": expected_ad,
    }


@pytest.mark.parametrize("enabled,secondary_enabled", [(True, "0"), (True, "1"), (False, "0")])
async def test_wifi_switch_uses_firmware_ad(modem, enabled, secondary_enabled):
    import hashlib

    client, state = modem
    state["m_ssid_enable"] = secondary_enabled
    await client.async_update()
    status = await client.async_set_wifi(enabled)
    assert status["RadioOff"] == ("0" if enabled else "1")
    post = next(item for item in state["posts"] if item["goformId"] == "SET_WIFI_INFO")
    inner_hash = hashlib.md5(VERSION.encode()).hexdigest()
    expected_ad = hashlib.md5(f"{inner_hash}random-data".encode()).hexdigest()
    expected = {
        "isTest": "false",
        "goformId": "SET_WIFI_INFO",
        "wifiEnabled": "1" if enabled else "0",
        "AD": expected_ad,
    }
    if enabled:
        expected["m_ssid_enable"] = secondary_enabled
    assert post == expected


async def test_bad_password_only_attempted_once(modem):
    client, state = modem
    state["bad_auth"] = True
    with pytest.raises(InvalidAuth):
        await client.async_update()
    assert len(state["posts"]) == 1


async def test_empty_password_does_not_attempt_login(modem):
    client, state = modem
    client.password = ""
    with pytest.raises(InvalidAuth):
        await client.async_update()
    assert not state["posts"]


@pytest.mark.parametrize("failure", ["bad_json", "http_error", "missing_status"])
async def test_unusable_responses(modem, failure):
    client, state = modem
    state[failure] = True
    with pytest.raises(CannotConnect):
        await client.async_update()


@pytest.mark.parametrize(
    "host,expected",
    [
        ("192.168.0.1", "http://192.168.0.1"),
        ("http://MODEM.local:80/", "http://modem.local"),
        ("https://modem.local:8443", "https://modem.local:8443"),
        ("http://[::1]:8080/", "http://[::1]:8080"),
    ],
)
def test_host(host, expected):
    assert normalize_host(host) == expected


@pytest.mark.parametrize(
    "host",
    [
        "",
        "http://u:p@modem",
        "ftp://modem",
        "modem/path",
        "modem?password=secret",
        "modem:99999",
        "a b",
        "modem#x",
    ],
)
def test_invalid_host(host):
    with pytest.raises(ValueError):
        normalize_host(host)


def test_profiles_and_identity():
    assert select_profile("MF920U", "auto", VERSION) == PROFILES["mf920u_b10"]
    assert select_profile("MF920U", "mf920u_b10", "another version") == PROFILES["mf920u_b10"]
    for model, firmware in [("MF920U", "unknown"), ("MF999", "mf920u_b10"), ("MF920U", "auto")]:
        with pytest.raises(UnsupportedFirmware):
            select_profile(model, firmware, "unknown")
    assert device_id({"imei": "123456789012345"}) == "123456789012345"
    assert device_id({"mac_address": "AA:BB:CC:DD:EE:FF"}) == "aabbccddeeff"
    assert device_id({"imei": "000000000000000"}) is None
    assert device_id({}) is None
