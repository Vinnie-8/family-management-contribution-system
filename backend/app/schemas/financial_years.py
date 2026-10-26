"""Request/response schemas for financial years."""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.money import Balance


class FinancialYearCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    year: int = Field(ge=2000, le=2100, description="The label of the year, e.g. 2026")
    start_date: date
    end_date: date
    # Only for a family's first year. Later years carry the closing balance forward.
    opening_balance: Optional[Balance] = None

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class FinancialYearResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    year: int
    start_date: date
    end_date: date
    status: str
    opening_balance: Decimal
    closing_balance: Optional[Decimal] = None