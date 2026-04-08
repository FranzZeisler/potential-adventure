from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Aircraft:
    """Represents a tail number and its physical availability."""
    tail_number: str
    fleet_type: str
    is_aog: bool = False
    aog_start: Optional[datetime] = None
    aog_end: Optional[datetime] = None

    def is_available(self, start_time: datetime, end_time: datetime) -> bool:
        """Business Logic: Can this aircraft fly between these two times?"""
        if not self.is_aog:
            return True

        # Safety check: if marked AOG but no times given, assume fully unavailable
        if self.aog_start is None or self.aog_end is None:
            return False

        # It is available if the flight ends before AOG starts, or starts after AOG ends
        if end_time <= self.aog_start or start_time >= self.aog_end:
            return True

        return False
