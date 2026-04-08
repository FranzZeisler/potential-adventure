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
    delay_mins: int = 0
    route_cost: float = 8000.0

    id: str = field(init=False)
    base_flight_id: str = field(init=False)

    def __post_init__(self):
        self.base_flight_id = f"{self.flight_number}_{self.sched_dep.strftime('%Y%m%d')}"
        self.id = f"{self.base_flight_id}_D{self.delay_mins}"
        if self.delay_mins > 0:
            self.sched_dep += timedelta(minutes=self.delay_mins)
            self.sched_arr += timedelta(minutes=self.delay_mins)

    @property
    def duration(self) -> timedelta:
        return self.sched_arr - self.sched_dep

    @property
    def eu261_compensation(self) -> float:
        delay_hrs = self.delay_mins / 60.0
        if delay_hrs < 3:
            return 0.0
        duration_hrs = self.duration.total_seconds() / 3600
        if duration_hrs <= 2.0:
            per_pax = 250.0
        elif duration_hrs <= 3.5:
            per_pax = 400.0
        else:
            per_pax = 600.0
        return per_pax * self.pax_count
