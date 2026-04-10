from dataclasses import dataclass
from datetime import datetime
from typing import Optional

try:
    from config import OpsRules
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import OpsRules

@dataclass(frozen=True)
class Airport:
    code: str
    min_turnaround_mins: int = OpsRules.MIN_TURNAROUND_MINS
    curfew_start_hr: Optional[int] = OpsRules.DEFAULT_CURFEW_START
    curfew_end_hr: Optional[int] = OpsRules.DEFAULT_CURFEW_END
    maintenance_hub: bool = False
    airport_fee: float = 500.0

    def is_curfew_violated(self, time_to_check: datetime) -> bool:
        if self.curfew_start_hr is None or self.curfew_end_hr is None:
            return False
        hr = time_to_check.hour
        if self.curfew_start_hr > self.curfew_end_hr:
            return hr >= self.curfew_start_hr or hr < self.curfew_end_hr
        else:
            return self.curfew_start_hr <= hr < self.curfew_end_hr
