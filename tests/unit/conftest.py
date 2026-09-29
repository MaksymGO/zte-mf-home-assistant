"""Load the transport without importing Home Assistant on Windows."""

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "custom_components" / "zte_mf"
package = types.ModuleType("zte_transport")
package.__path__ = [str(ROOT)]
sys.modules["zte_transport"] = package
for name in ("profiles", "api"):
    spec = importlib.util.spec_from_file_location(f"zte_transport.{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
