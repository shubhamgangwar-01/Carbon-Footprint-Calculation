import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("AUTO_MIGRATE", "false")
os.environ.setdefault("SECRET_KEY", "test-secret")

from app.calculations.factor_repository import FactorRepository  # noqa: E402
from app.schemas.conference import ConferenceInput  # noqa: E402
from app.services.emissions_engine import EmissionsEngine  # noqa: E402

FACTORS_JSON = ROOT / "data" / "processed" / "emission_factors.json"


@pytest.fixture(scope="session")
def repo() -> FactorRepository:
    return FactorRepository.from_json(FACTORS_JSON)


@pytest.fixture(scope="session")
def F(repo):
    """F('key') -> active factor value, read straight from the processed database."""
    return lambda key: repo.get(key).value


@pytest.fixture
def calc(repo):
    def _run(data: dict):
        base = {"basic": {"name": "T", "attendees": 100, "days": 2, "country_code": "IN"}}
        for k, v in data.items():
            if k == "basic":
                base["basic"].update(v)
            else:
                base[k] = v
        return EmissionsEngine(repo).calculate(ConferenceInput.model_validate(base))
    return _run


def load_sample(name: str) -> dict:
    return json.loads((ROOT / "data" / "samples" / f"{name}.json").read_text())["input"]
