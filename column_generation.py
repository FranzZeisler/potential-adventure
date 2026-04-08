import sys, os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ortools.linear_solver import pywraplp
from typing import List, Tuple, Dict, Optional
from datetime import timedelta
from domain.flight import Flight
from domain.aircraft import Aircraft
from domain.rotation import Rotation
from config import Costs, SolverSettings


class RecoveryOptimizer:

    def __init__(self, flights: List[Flight],
                 aircraft_fleet: List[Aircraft],
                 crew_roster: Optional[dict] = None):
        self.aircraft_fleet = aircraft_fleet
        self.cancel_penalty = Costs.CANCEL_FLIGHT
        self.generated_rotations: List[Rotation] = []
        self.crew_roster = crew_roster or {}

        # --- THE DISCRETIZED DELAY EXPANSION ---
        self.flights = []
        self.base_flight_ids = set()

        for base_flight in flights:
            self.base_flight_ids.add(base_flight.base_flight_id)

            # Create the On-Time copy
            self.flights.append(base_flight)

            # Create delayed copies (e.g., +60 mins, +120 mins)
            for delay in [60, 120, 180]:
                delayed_copy = Flight(
                    flight_number=base_flight.flight_number,
                    dep_airport=base_flight.dep_airport,
                    arr_airport=base_flight.arr_airport,
                    sched_dep=base_flight.sched_dep -
                    timedelta(minutes=base_flight.delay_mins),
                    sched_arr=base_flight.sched_arr -
                    timedelta(minutes=base_flight.delay_mins),
                    delay_mins=delay,
                    pax_count=base_flight.pax_count,
                    route_cost=base_flight.route_cost,
                )
                self.flights.append(delayed_copy)

    def _solve_master_problem(
        self, relaxed: bool
    ) -> Tuple[float, Dict[str, float], List[Rotation], List[str]]:
        solver_type = 'GLOP' if relaxed else 'SCIP'
        solver = pywraplp.Solver.CreateSolver(solver_type)

        lam = {
            idx:
                solver.NumVar(0, 1, f'lam_{idx}') if relaxed else solver.IntVar(
                    0, 1, f'lam_{idx}')
            for idx in range(len(self.generated_rotations))
        }

        # Cancellations are now based on the BASE FLIGHT ID, not the specific delayed copy
        y = {
            base_id:
                solver.NumVar(0, 1, f'y_{base_id}')
                if relaxed else solver.IntVar(0, 1, f'y_{base_id}')
            for base_id in self.base_flight_ids
        }

        coverage_constraints = {}
        for base_id in self.base_flight_ids:
            # Find all rotations that contain ANY version of this base flight
            expr = []
            for idx, rot in enumerate(self.generated_rotations):
                # Check if this rotation contains a flight matching the base_id
                if any(f.base_flight_id == base_id for f in rot.flights):
                    expr.append(lam[idx])

            coverage_constraints[base_id] = solver.Add(
                solver.Sum(expr) + y[base_id] == 1)

        for ac in self.aircraft_fleet:
            expr = [
                lam[idx]
                for idx, rot in enumerate(self.generated_rotations)
                if rot.aircraft.tail_number == ac.tail_number
            ]
            solver.Add(solver.Sum(expr) <= 1)

        objective = solver.Objective()
        for idx, rot in enumerate(self.generated_rotations):
            objective.SetCoefficient(lam[idx], rot.cost)
        for base_id in self.base_flight_ids:
            objective.SetCoefficient(y[base_id], self.cancel_penalty)
        objective.SetMinimization()

        status = solver.Solve()

        if status != pywraplp.Solver.OPTIMAL:
            return float('inf'), {}, [], []

        if relaxed:
            duals = {
                base_id: coverage_constraints[base_id].dual_value()
                for base_id in self.base_flight_ids
            }
            return objective.Value(), duals, [], []
        else:
            selected_rotations = [
                self.generated_rotations[i]
                for i in lam
                if lam[i].solution_value() > 0.5
            ]
            cancelled_flights = [
                base_id for base_id in self.base_flight_ids
                if y[base_id].solution_value() > 0.5
            ]
            return objective.Value(), {}, selected_rotations, cancelled_flights

    def _solve_pricing_subproblem(self, duals: Dict[str,
                                                    float]) -> List[Rotation]:
        new_columns = []
        for ac in self.aircraft_fleet:
            for start_flight in self.flights:

                rot1 = Rotation([start_flight], ac, self.crew_roster)
                if rot1.is_feasible and (
                        rot1.cost - duals[start_flight.base_flight_id] < -0.01):
                    new_columns.append(rot1)

                    for f2 in self.flights:
                        # Prevent using two versions of the exact same flight in one rotation
                        if start_flight.base_flight_id == f2.base_flight_id:
                            continue

                        rot2 = Rotation([start_flight, f2], ac, self.crew_roster)
                        if rot2.is_feasible and (
                                rot2.cost -
                            (duals[start_flight.base_flight_id] +
                             duals[f2.base_flight_id]) < -0.01):
                            new_columns.append(rot2)

        return new_columns

    def run(self, max_iterations: int = 15):
        print(
            f"\n[OR-Tools] Expanding {len(self.base_flight_ids)} flights into {len(self.flights)} temporal copies..."
        )
        for iteration in range(max_iterations):
            obj_val, duals, _, _ = self._solve_master_problem(relaxed=True)
            if not duals:
                break

            new_columns = self._solve_pricing_subproblem(duals)
            if not new_columns:
                break

            self.generated_rotations.extend(new_columns)

        final_obj, _, final_rotations, cancellations = self._solve_master_problem(
            relaxed=False)
        return {
            "status": "Success" if final_obj != float('inf') else "Failed",
            "cost": final_obj,
            "rotations": final_rotations,
            "cancelled_flight_ids": cancellations,
            "total_columns_generated": len(self.generated_rotations)
        }
