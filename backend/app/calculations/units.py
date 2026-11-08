"""Unit normalisation. Every activity quantity is converted to the factor's
activity unit before multiplication. Unknown units raise instead of guessing."""
from __future__ import annotations

KM_PER_MILE = 1.609344            # international mile (exact)
L_PER_US_GALLON = 3.785411784     # exact
L_PER_UK_GALLON = 4.54609         # exact
KG_PER_LB = 0.45359237            # exact
KWH_PER_GJ = 1000 / 3.6           # 1 kWh = 3.6 MJ

# ISO 216 sheet areas in m^2
SHEET_AREA_M2 = {"A3": 0.297 * 0.420, "A4": 0.210 * 0.297, "A5": 0.148 * 0.210}

_MASS = {"kg": 1.0, "g": 0.001, "tonne": 1000.0, "t": 1000.0, "lb": KG_PER_LB}
_DIST = {"km": 1.0, "miles": KM_PER_MILE, "mi": KM_PER_MILE, "m": 0.001}
_VOL = {"litre": 1.0, "l": 1.0, "litres": 1.0, "m3": 1000.0, "us_gallon": L_PER_US_GALLON, "uk_gallon": L_PER_UK_GALLON}
_ENERGY = {"kwh": 1.0, "mwh": 1000.0, "gj": KWH_PER_GJ}


class UnitError(ValueError):
    pass


def to_kg(value: float, unit: str) -> float:
    try:
        return value * _MASS[unit.lower()]
    except KeyError as e:
        raise UnitError(f"Unknown mass unit '{unit}'") from e


def to_km(value: float, unit: str) -> float:
    try:
        return value * _DIST[unit.lower()]
    except KeyError as e:
        raise UnitError(f"Unknown distance unit '{unit}'") from e


def to_litres(value: float, unit: str) -> float:
    try:
        return value * _VOL[unit.lower()]
    except KeyError as e:
        raise UnitError(f"Unknown volume unit '{unit}'") from e


def to_kwh(value: float, unit: str) -> float:
    try:
        return value * _ENERGY[unit.lower()]
    except KeyError as e:
        raise UnitError(f"Unknown energy unit '{unit}'") from e


def pages_to_paper_kg(pages: float, gsm: float, sheet: str = "A4", double_sided: bool = False) -> float:
    """Printed pages -> paper mass. sheets = pages / 2 when double-sided (rounded up per job is ignored)."""
    if sheet not in SHEET_AREA_M2:
        raise UnitError(f"Unknown sheet size '{sheet}'")
    sheets = pages / 2 if double_sided else pages
    return sheets * SHEET_AREA_M2[sheet] * gsm / 1000.0
