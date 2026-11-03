"""Response schemas for the welfare fund."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class MovementResponse(BaseModel):
    when: datetime
    kind: str          # "payment", "fine_payment" or "expense"
    description: str
    amount: Decimal    # positive = money in, negative = money out
    reference_id: uuid.UUID


class StandingFundResponse(BaseModel):
    id: uuid.UUID
    name: str
    balance: Decimal
    movements: List[MovementResponse] = []