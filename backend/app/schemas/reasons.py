"""A reason typed by a person for a reject, void, waive or cancel. It goes into the audit log."""
from typing import Annotated

from pydantic import StringConstraints

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=300)]