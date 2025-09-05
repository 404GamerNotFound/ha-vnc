import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "vnc_const", Path(__file__).parent.parent / "custom_components" / "vnc" / "const.py"
)
const = importlib.util.module_from_spec(spec)
spec.loader.exec_module(const)


def test_constants():
    assert const.DOMAIN == "vnc"
    assert const.DEFAULT_PORT == 5900
