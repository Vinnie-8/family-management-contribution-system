"""Shared money types. Money is Decimal in KES, never float.

In JSON requests, send amounts as numbers or strings ("2000" or "2000.50").
In JSON responses, amounts come back as strings ("2000.00"), which is the
safe way to carry money across JSON without rounding.
"""
from decimal import Decimal
from typing import Annotated

from pydantic import Field

# A positive amount: a rule, a pledge, a payment, a fine, an expense.
Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]

# An opening balance can be zero.
Balance = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]