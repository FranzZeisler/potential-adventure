from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class Aircraft:
    tail_number: str
    fleet_type: str
    is_aog: bool = False
    aog_start: Optional[datetime] = None
    aog_end: Optional[datetime] = None
    crew_ids: List[str] = field(default_factory=list)

    def is_available(self, start_time: datetime, end_time: datetime) -> bool:
        if not self.is_aog:
            return True
        if self.aog_start is None or self.aog_end is None:
            return False
        if end_time <= self.aog_start or start_time >= self.aog_end:
            return True
        return False
