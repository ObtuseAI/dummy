import json
from pathlib import Path
from core.ontology import CapConfig

CONFIG_DIR = Path(__file__).parent.parent / "configs"

def load_caps() -> CapConfig:
    with (CONFIG_DIR / "caps.json").open() as f:
        return CapConfig.model_validate(json.load(f))

def load_allowlists() -> dict:
    path = CONFIG_DIR / "allowlists.json"
    if not path.exists():
        return {"markets": [], "categories": []}
    return json.loads(path.read_text())
