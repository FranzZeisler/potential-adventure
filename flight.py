from dataclasses import dataclass, field
from datetime import datetime, timedelta
from .airport import Airport


@dataclass
class Flight:
    flight_number: str
    dep_airport: Airport
    arr_airport: Airport
    sched_dep: datetime
    sched_arr: datetime
    pax_count: int = 160

    # NEW: Track how delayed this specific copy is
    delay_mins: int = 0

    id: str = field(init=False)
    base_flight_id: str = field(init=False)

    def __post_init__(self):
        # Base ID identifies the original scheduled flight (e.g., XQ123_20260408)
        self.base_flight_id = f"{self.flight_number}_{self.sched_dep.strftime('%Y%m%d')}"

        # Unique ID for this specific delayed copy (e.g., XQ123_20260408_D60)
        self.id = f"{self.base_flight_id}_D{self.delay_mins}"

        # Physically shift the times based on the delay
        if self.delay_mins > 0:
            self.sched_dep += timedelta(minutes=self.delay_mins)
            self.sched_arr += timedelta(minutes=self.delay_mins)

    @property
    def duration(self) -> timedelta:
        return self.sched_arr - self.sched_dep
