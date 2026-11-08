"""Emission-factor lookup with version control.

The engine never touches raw numbers directly: it asks the repository for a
logical `factor_key` (e.g. "electricity.grid.IN"), and the repository returns
the active record for the requested factor-set version. Every record carries
its own `factor_id` (key@dataset_version) which is stored with each
calculation line, so historical results stay reproducible after updates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_JSON = Path(__file__).resolve().parents[3] / "data" / "processed" / "emission_factors.json"


class FactorNotFound(KeyError):
    pass


@dataclass(frozen=True)
class Factor:
    factor_id: str
    factor_key: str
    category: str
    activity: str
    subcategory: str
    value: float
    unit: str
    activity_unit: str
    geography: str
    reporting_year: str
    source_name: str
    source_url: str
    dataset_version: str
    data_quality_label: str
    data_quality_score: float
    system_boundary: str
    is_active: bool
    raw: dict

    @classmethod
    def from_record(cls, r: dict) -> "Factor":
        dq = r.get("data_quality") or {}
        return cls(
            factor_id=r["factor_id"], factor_key=r["factor_key"], category=r["category"], activity=r["activity"],
            subcategory=r["subcategory"], value=float(r["emission_factor"]), unit=r["unit"],
            activity_unit=r["activity_unit"], geography=r["geography"], reporting_year=str(r["reporting_year"]),
            source_name=r["source_name"], source_url=r["source_url"], dataset_version=r["dataset_version"],
            data_quality_label=dq.get("label", "low"), data_quality_score=float(dq.get("score", 3.0)),
            system_boundary=r.get("system_boundary", ""), is_active=bool(r.get("is_active", True)), raw=r,
        )


class FactorRepository:
    def __init__(self, records: Iterable[dict], factor_set_version: str = "FS-2026.1"):
        self.factor_set_version = factor_set_version
        self._by_id: dict[str, Factor] = {}
        self._active: dict[str, Factor] = {}
        for r in records:
            f = Factor.from_record(r)
            self._by_id[f.factor_id] = f
            if f.is_active:
                if f.factor_key in self._active:
                    raise ValueError(f"Two active factors for key {f.factor_key}: "
                                     f"{self._active[f.factor_key].factor_id} and {f.factor_id}")
                self._active[f.factor_key] = f

    @classmethod
    def from_json(cls, path: Path | str = DEFAULT_JSON) -> "FactorRepository":
        db = json.loads(Path(path).read_text())
        return cls(db["factors"], db.get("factor_set_version", "unknown"))

    def get(self, key: str, pinned: Optional[dict[str, str]] = None) -> Factor:
        """Return the active factor for `key`, or the pinned factor_id if a pin map is supplied
        (used to recompute a historical calculation with exactly the same factors)."""
        if pinned and key in pinned:
            fid = pinned[key]
            if fid not in self._by_id:
                raise FactorNotFound(f"Pinned factor {fid} no longer exists")
            return self._by_id[fid]
        if key not in self._active:
            raise FactorNotFound(key)
        return self._active[key]

    def has(self, key: str) -> bool:
        return key in self._active

    def by_id(self, factor_id: str) -> Factor:
        return self._by_id[factor_id]

    def active(self) -> list[Factor]:
        return list(self._active.values())

    def all(self) -> list[Factor]:
        return list(self._by_id.values())

    def keys_with_prefix(self, prefix: str) -> list[str]:
        return sorted(k for k in self._active if k.startswith(prefix))
