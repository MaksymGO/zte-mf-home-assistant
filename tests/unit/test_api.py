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
    }

    async def get(request):
        if state["http_error"]:
            return web.Response(status=503)
        if state["bad_json"]:
            return web.Response(text="<html>error</html>")
        commands = request.query["cmd"]
        if commands == "wa_inner_version":
            return web.json_response({"wa_inner_version": VERSION})
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
                "ppp_status": "ppp_connected",
                "battery_vol_percent": "75",
            }
        )

    async def post(request):
        data = dict(await request.post())
        state["posts"].append(data)
        assert request.headers["Referer"].endswith("/index.html")
        assert data["goformId"] == "LOGIN"
        if state["bad_auth"]:
            return web.json_response({"result": "3"})
        result = web.json_response({"result": "0"})
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
