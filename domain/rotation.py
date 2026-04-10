from datetime import timedelta
from typing import List, Optional

try:
    from config import Costs
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Costs

from .flight import Flight
from .aircraft import Aircraft

class Rotation:
    def __init__(self, flights: List[Flight], aircraft: Aircraft, crew_roster: Optional[dict] = None):
        self.flights = sorted(flights, key=lambda f: f.sched_dep)
        self.aircraft = aircraft
        self.flight_ids = {f.id for f in self.flights}
        self.crew_roster = crew_roster or {}
        self.is_feasible = True
        self.infeasibility_reason = ""
        self.cost = 0.0
        self.cost_breakdown: dict = {}
        self.total_delay_mins = sum(f.delay_mins for f in self.flights)
        self._evaluate_rotation()

    def _evaluate_rotation(self):
        if not self.flights:
            self.is_feasible = False
            self.infeasibility_reason = "Empty rotation"
            return

        dispatch_cost = len(self.flights) * Costs.DISPATCH_BASE
        delay_penalty = self.total_delay_mins * Costs.DELAY_COST_PER_MIN
        subcharter_cost = 0.0
        curfew_cost = 0.0
        ferry_cost = 0.0
        airport_fee_cost = 0.0
        route_cost = 0.0
        eu261_cost = 0.0
        type_cert_cost = 0.0

        if self.aircraft.fleet_type == "Subcharter":
            subcharter_cost = Costs.SUBCHARTER_BASE
        if self.aircraft.fleet_type == "Reserve Aircraft":
            subcharter_cost += Costs.RESERVE_AIRCRAFT_COST

        for crew_id in self.aircraft.crew_ids:
            crew = self.crew_roster.get(crew_id)
            if crew and not crew.can_fly(self.aircraft.fleet_type):
                type_cert_cost += Costs.TYPE_CERT_CREW_SWAP
                break

        for i, current_flight in enumerate(self.flights):
            route_cost += current_flight.route_cost
            airport_fee_cost += current_flight.arr_airport.airport_fee
            eu261_cost += current_flight.eu261_compensation

            if not self.aircraft.is_available(current_flight.sched_dep, current_flight.sched_arr):
                self.is_feasible = False
                self.infeasibility_reason = f"AOG conflict for {self.aircraft.tail_number}"
                return

            for crew_id in self.aircraft.crew_ids:
                crew = self.crew_roster.get(crew_id)
                if crew and not crew.is_within_duty(current_flight.sched_dep, current_flight.sched_arr):
                    self.is_feasible = False
                    self.infeasibility_reason = f"Crew duty limit exceeded for {crew_id}"
                    return

            if current_flight.dep_airport.is_curfew_violated(current_flight.sched_dep):
                curfew_cost += Costs.CURFEW_VIOLATION
            if current_flight.arr_airport.is_curfew_violated(current_flight.sched_arr):
                curfew_cost += Costs.CURFEW_VIOLATION

            if i > 0:
                prev_flight = self.flights[i - 1]
                if prev_flight.arr_airport.code != current_flight.dep_airport.code:
                    if self.aircraft.fleet_type == "Subcharter":
                        pass
                    else:
                        ferry_flight_time = timedelta(hours=2, minutes=30)
                        min_turnaround = timedelta(minutes=prev_flight.arr_airport.min_turnaround_mins)
                        time_needed = ferry_flight_time + min_turnaround
                        time_available = current_flight.sched_dep - prev_flight.sched_arr
                        if time_available < time_needed:
                            self.is_feasible = False
                            self.infeasibility_reason = f"Insufficient time to ferry from {prev_flight.arr_airport.code} to {current_flight.dep_airport.code}"
                            return
                        else:
                            ferry_cost += Costs.FERRY_FLIGHT_FLAT
                else:
                    min_turnaround = timedelta(minutes=prev_flight.arr_airport.min_turnaround_mins)
                    actual_turnaround = current_flight.sched_dep - prev_flight.sched_arr
                    if actual_turnaround < min_turnaround:
                        self.is_feasible = False
                        self.infeasibility_reason = "Insufficient turnaround time"
                        return

        self.cost_breakdown = {
            "dispatch": dispatch_cost,
            "delay_penalty": delay_penalty,
            "route": route_cost,
            "airport_fees": airport_fee_cost,
            "eu261": eu261_cost,
            "curfew": curfew_cost,
            "ferry": ferry_cost,
            "subcharter_reserve": subcharter_cost,
            "type_cert": type_cert_cost,
        }
        self.cost = sum(self.cost_breakdown.values())
