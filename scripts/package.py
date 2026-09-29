"""Build a deterministic file list without secrets or bytecode."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def build():
    target = ROOT / "dist" / "zte_mf.zip"
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for source in sorted((ROOT / "custom_components" / "zte_mf").rglob("*")):
            if source.is_file() and (
                source.suffix in {".py", ".json"}
                or (source.parent.name == "brand" and source.suffix == ".png")
            ):
                archive.write(source, source.relative_to(ROOT))
    return target


if __name__ == "__main__":
    print(build())
