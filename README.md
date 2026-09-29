# ZTE MF for Home Assistant

A local custom integration for ZTE MF-series modems, configured through the Home Assistant UI.
The initial supported model is **ZTE MF920U**, with firmware profile **BD_CNCNLMF920UV1.0.0B10**.
Additional models and API variants can be added as separate profiles.

[![Open HACS Repository on my HA](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MaksymGO&repository=zte-mf-home-assistant&category=integration)
[![Add integration to my HA](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=zte_mf)

The HACS button requires HACS to be installed. Install ZTE MF and restart Home Assistant
before using the **Add integration to my HA** button.

## Features

- Configure the address, model, firmware profile, and password through the UI.
- Automatically detect known firmware or select a profile manually.
- Reconfigure the address/profile and reauthenticate when the password changes.
- Separate cookie sessions for each modem, with recovery after session expiration.
- Poll every 30 seconds by default, configurable from 10 to 3600 seconds.
- Stable device identity based on IMEI or MAC, independent of the IP address or SIM.
- English and Ukrainian configuration forms.

| Entities | Measurements |
| --- | --- |
| Network | Operator, network type, SIM status, mobile connection, roaming |
| Signal | Signal bars, RSSI, RSCP, LTE RSRP |
| Power | Battery level, charging status |
| Traffic | Bytes sent/received per session, transfer rates in B/s, connection duration |

Missing or invalid readings become `unknown`; entities become `unavailable` when
communication fails. Traffic counters may reset after reconnection.
RSSI/RSCP/RSRP availability depends on the network type and firmware.
The integration reads telemetry; its only POST operation is logging in to the web interface.

## Compatibility

Requires Home Assistant **2025.1+** and network access from HA to the modem.
Goform API availability and the firmware version were verified on the device at
`192.168.0.1`. Commands and the login procedure were checked against the JavaScript
in the device's web interface.
The device returns empty readings without authentication. A complete login and live
telemetry still need to be verified using your password after installation.
HTTP tests simulate modem responses; HA tests run in the actual Home Assistant test runtime.

Only MF920U is currently listed. Untested models are not advertised as supported.
`Automatic` requires an exact match with a known firmware version. Manual selection
applies the selected profile regardless of the version string, allowing compatible
variants to be tested without guaranteeing support. The integration does not change
the modem's firmware.

## Installation

### Manual installation / develop branch

1. Copy `custom_components/zte_mf` to `/config/custom_components/zte_mf` on HA.
   Alternatively, extract the GitHub Release ZIP into `/config`; the archive already
   contains this directory structure.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → ZTE MF**.
4. Enter `192.168.0.1`, select `MF920U`, choose `Automatic` or the B10 profile,
   and enter the **modem web interface password** (not the Wi-Fi password or SIM PIN).

No YAML configuration is required. The address may include `http://` / `https://`
and a port. Use **Reconfigure** in the integration menu to change the address,
profile, or password. Leaving the password blank during reconfiguration preserves
the saved password. Add a new integration for a different physical modem.

### HACS

Add `https://github.com/MaksymGO/zte-mf-home-assistant` as a custom repository
of type **Integration**, install ZTE MF, and restart HA. This does not imply inclusion
in the default HACS catalog. Use HACS after the first release from `main`;
use manual installation for the current `develop` branch.

The password is stored in the HA config entry; do not include it in Git or issues.
This firmware uses Base64 over HTTP. Base64 does not encrypt the password, so
the web interface should remain on a trusted local network.
If the password is rejected, HA requests reauthentication instead of repeatedly
attempting to log in.

## Adding models and firmware profiles

The registry is in `custom_components/zte_mf/profiles.py`:

1. Verify the new model's web interface requests, field names, units, and login procedure.
2. Add a `FirmwareProfile` to `PROFILES` with a stable key, model, and exact firmware
   version. The model/profile lists in the UI are generated automatically.
3. For a different authentication method, add a strategy to `api.py`. Currently,
   only Base64 LOGIN is implemented; SHA/challenge authentication is not supported.
4. If fields or units differ, normalize them to the canonical sensor fields in
   the profile/client and add tests.
5. Add anonymized response samples and tests before declaring support.

Profiles contain API paths, the login command, password encoding, and polling commands.
Adding a profile does not require changes to the model/firmware selection form.

## Development

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest tests/unit
python scripts/validate.py
python scripts/package.py
```

Run HA tests in a separate Linux environment with Python 3.14.
The test dependency is pinned for Home Assistant 2026.9.4.

```sh
pip install -r requirements-ha-test.txt
pytest tests/ha
```

Unit tests cover HTTP/JSON, cookies for IP addresses, login recovery, errors,
addresses, and profiles. HA tests cover configuration forms, duplicate entries,
reauthentication, entities, options, and unloading.
CI runs these checks and Hassfest on pushes and pull requests to `develop` and `main`.

## GitHub CI/CD and versioning

Development takes place on `develop`; changes reach `main` through pull requests.
The release workflow runs only on `main`, including manual runs, and requires
successful CI checks. Use Conventional Commits for squash commit titles:

- `fix: ...` — patch release.
- `feat: ...` — minor release.
- `feat!: ...` / `BREAKING CHANGE:` — breaking change (a minor release before 1.0).

Release Please automatically creates a release PR targeting `main`, updating
`CHANGELOG.md`, `version.txt`, `.release-please-manifest.json`, and the version in
`manifest.json`. Merging that PR creates a `vX.Y.Z` tag, a GitHub Release, and a ZIP
built from the tagged code. The initial code version is `0.1.0`; pushes to `develop`
do not each create a release. Merging the release PR is the explicit release approval step.

In GitHub, under **Settings → Actions → General → Workflow permissions**, allow
GitHub Actions to create pull requests. Only the release job receives
`contents: write` and `pull-requests: write` permissions. `GITHUB_TOKEN` is usually sufficient.
PRs created with that token do not automatically trigger new workflows. If branch
protection requires PR checks, run CI manually for the release PR branch or configure
a GitHub App token for Release Please. CI still runs on `main` before the actual release.
After a release, synchronize `main` back into `develop`.

## Sources

- Device API: `js/service.js`, `js/login.js`, and `js/config/ufi/mfxxx/config.js`
  from the tested MF920U, inspected on September 29, 2026. Modem files are not included
  in this repository.
- [HA config flows](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [HA coordinator](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Release Please Action](https://github.com/googleapis/release-please-action)
