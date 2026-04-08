from datetime import timedelta
from typing import List
from config import Costs
from .flight import Flight
from .aircraft import Aircraft


class Rotation:

    def __init__(self, flights: List[Flight], aircraft: Aircraft):
        self.flights = sorted(flights, key=lambda f: f.sched_dep)
        self.aircraft = aircraft
        self.flight_ids = {f.id for f in self.flights}

        self.is_feasible = True
        self.infeasibility_reason = ""
        self.cost = 0.0
        self.total_delay_mins = sum(f.delay_mins for f in self.flights)

        self._evaluate_rotation()

    def _evaluate_rotation(self):
        # 1. Base Dispatch + Delay Penalty
        self.cost = (len(self.flights) *
                     Costs.DISPATCH_BASE) + (self.total_delay_mins * 85.0)

        # 2. Subcharter Base Cost
        if self.aircraft.fleet_type == "Subcharter":
            self.cost += Costs.SUBCHARTER_BASE

        if not self.flights:
            self.is_feasible = False
            self.infeasibility_reason = "Empty rotation"
            return

        for i in range(len(self.flights)):
            current_flight = self.flights[i]

            # --- Rule A: Aircraft Availability ---
            if not self.aircraft.is_available(current_flight.sched_dep,
                                              current_flight.sched_arr):
                self.is_feasible = False
                self.infeasibility_reason = f"AOG conflict for {self.aircraft.tail_number}"
                return

            # --- Rule B: Curfews ---
            if current_flight.dep_airport.is_curfew_violated(
                    current_flight.sched_dep):
                self.cost += Costs.CURFEW_VIOLATION
            if current_flight.arr_airport.is_curfew_violated(
                    current_flight.sched_arr):
                self.cost += Costs.CURFEW_VIOLATION

            # --- Rule C: Turnaround & Ferry Flights ---
            if i > 0:
                prev_flight = self.flights[i - 1]

                # C1: Do locations match?
                if prev_flight.arr_airport.code != current_flight.dep_airport.code:

                    # If it's a subcharter, we assume the ACMI provider repositions it for us magically
                    if self.aircraft.fleet_type == "Subcharter":
                        pass
                    else:
                        # It is our own plane. We must fly an empty FERRY leg.
                        # POC Heuristic: Assume an average European ferry flight takes 2.5 hours
                        ferry_flight_time = timedelta(hours=2, minutes=30)
                        min_turnaround = timedelta(
                            minutes=prev_flight.arr_airport.min_turnaround_mins)

                        time_needed_to_ferry = ferry_flight_time + min_turnaround
                        time_available = current_flight.sched_dep - prev_flight.sched_arr

                        if time_available < time_needed_to_ferry:
                            self.is_feasible = False
                            self.infeasibility_reason = f"Insufficient time to ferry from {prev_flight.arr_airport.code} to {current_flight.dep_airport.code}"
                            return
                        else:
                            # It is physically possible! But we add a massive financial penalty.
                            self.cost += Costs.FERRY_FLIGHT_FLAT
                else:
                    # Locations match, just check standard turnaround time
                    min_turnaround = timedelta(
                        minutes=prev_flight.arr_airport.min_turnaround_mins)
                    actual_turnaround = current_flight.sched_dep - prev_flight.sched_arr

                    if actual_turnaround < min_turnaround:
                        self.is_feasible = False
                        self.infeasibility_reason = "Insufficient turnaround time"
                        return
