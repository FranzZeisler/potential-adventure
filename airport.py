from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from config import OpsRules


@dataclass(frozen=True)
class Airport:
    """Represents a physical location in the network."""
    code: str
    min_turnaround_mins: int = OpsRules.MIN_TURNAROUND_MINS
    curfew_start_hr: Optional[int] = OpsRules.DEFAULT_CURFEW_START
    curfew_end_hr: Optional[int] = OpsRules.DEFAULT_CURFEW_END
    maintenance_hub: bool = False

    def is_curfew_violated(self, time_to_check: datetime) -> bool:
        """Business Logic: Checks if an operation happens during curfew."""
        if self.curfew_start_hr is None or self.curfew_end_hr is None:
            return False

        hr = time_to_check.hour
        if self.curfew_start_hr > self.curfew_end_hr:  # e.g., 23:00 to 05:00
            return hr >= self.curfew_start_hr or hr < self.curfew_end_hr
        else:
            return self.curfew_start_hr <= hr < self.curfew_end_hr
