from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Set

@dataclass
class CrewMember:
    employee_id: str
    name: str
    role: str
    type_ratings: Set[str] = field(default_factory=set)
    duty_start: Optional[datetime] = None
    max_fdp_hours: float = 13.0
    min_rest_hours: float = 11.0

    def can_fly(self, fleet_type: str) -> bool:
        return fleet_type in self.type_ratings

    def is_within_duty(self, dep_time: datetime, arr_time: datetime) -> bool:
        if self.duty_start is None:
            return True
        fdp_end = self.duty_start + timedelta(hours=self.max_fdp_hours)
        return arr_time <= fdp_end

    def duty_hours_remaining(self, ref_time: datetime) -> float:
        if self.duty_start is None:
            return self.max_fdp_hours
        elapsed = (ref_time - self.duty_start).total_seconds() / 3600
        return max(0.0, self.max_fdp_hours - elapsed)
