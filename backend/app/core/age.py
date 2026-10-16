"""Age calculation shared by the Member model, the onboarding service and the daily job."""
from datetime import date
from typing import Optional


def age_in_years(born: date, today: Optional[date] = None) -> int:
    """Whole years since `born`. The tuple comparison takes a year off if this
    year's birthday hasn't happened yet."""
    today = today or date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))