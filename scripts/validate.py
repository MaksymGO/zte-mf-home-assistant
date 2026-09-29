"""Check release metadata and translation completeness without running HA."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    component = ROOT / "custom_components" / "zte_mf"
    manifest = json.loads((component / "manifest.json").read_text())
    version = manifest["version"]
    assert version == (ROOT / "version.txt").read_text().strip()
    assert version == json.loads((ROOT / ".release-please-manifest.json").read_text())["."]
    strings = json.loads((component / "strings.json").read_text(encoding="utf-8"))

    def keys(obj, prefix=""):
        return {
            item
            for key, value in obj.items()
            for item in (
                keys(value, prefix + key + ".") if isinstance(value, dict) else {prefix + key}
            )
        }

    for translation in (component / "translations").glob("*.json"):
        assert keys(json.loads(translation.read_text(encoding="utf-8"))) == keys(strings)
    print(f"Metadata and translations valid ({version})")


if __name__ == "__main__":
    main()
