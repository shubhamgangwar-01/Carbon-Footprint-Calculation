from __future__ import annotations

from fastapi import Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import CalculationResultRow, Conference, User
from app.schemas.conference import ConferenceInput
from app.services.auth import current_user


def own_conference(conf_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Conference:
    conf = db.get(Conference, conf_id)
    if not conf or (conf.owner_id != user.id and user.role != "admin"):
        raise HTTPException(404, "Conference not found")
    return conf


def own_calculation(calc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> CalculationResultRow:
    calc = db.get(CalculationResultRow, calc_id)
    if not calc or (calc.conference.owner_id != user.id and user.role != "admin"):
        raise HTTPException(404, "Calculation not found")
    return calc


def parse_input(data: dict) -> ConferenceInput:
    try:
        return ConferenceInput.model_validate(data)
    except ValidationError as ex:
        raise HTTPException(422, detail=[{"loc": e["loc"], "msg": e["msg"]} for e in ex.errors()])
