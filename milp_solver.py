"""
milp_solver.py — MILP-based flight recovery optimizer.

Replaces the column-generation / rotation approach.
Uses OR-Tools SCIP to solve a binary assignment problem:
  x[flight, aircraft] = 1  →  aircraft covers that flight
  cancel[flight]      = 1  →  flight is cancelled
"""
from ortools.linear_solver import pywraplp
from typing import List, Optional
from datetime import timedelta

from domain.flight import Flight
from domain.aircraft import Aircraft
from config import Costs


class MILPRecoveryOptimizer:
    """
    Mixed-Integer Linear Programme for disruption recovery.

    Decisions
    ---------
    x[i, j]   – binary: aircraft j operates flight i
    cancel[i] – binary: flight i is cancelled

    Constraints
    -----------
    1. Coverage  : each flight assigned to exactly one aircraft OR cancelled
    2. AOG       : grounded aircraft cannot cover conflicting flights
    3. Conflict  : no two time-overlapping flights on the same aircraft
                   (overlap test includes minimum turnaround buffer)

    Objective
    ---------
    Minimise  Σ cancel[i]·cancel_penalty  +  Σ x[i,j]·(route_cost + airport_fee + dispatch)
    """

    def __init__(
        self,
        flights: List[Flight],
        aircraft_fleet: List[Aircraft],
        crew_roster: Optional[dict] = None,
    ):
        self.flights = flights
        self.aircraft_fleet = aircraft_fleet
        self.crew_roster = crew_roster or {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _conflicts(self, f1: Flight, f2: Flight, turnaround_mins: int = 45) -> bool:
        """Return True when f1 and f2 cannot share the same aircraft."""
        buf = timedelta(minutes=turnaround_mins)
        return not (f1.sched_arr + buf <= f2.sched_dep or
                    f2.sched_arr + buf <= f1.sched_dep)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> dict:
        solver = pywraplp.Solver.CreateSolver("SCIP")
        if not solver:
            return self._failure()

        F = self.flights
        A = self.aircraft_fleet
        nF, nA = len(F), len(A)

        if nF == 0 or nA == 0:
            return self._failure()

        # --- Decision variables ---
        x = {
            (i, j): solver.IntVar(0, 1, f"x_{i}_{j}")
            for i in range(nF) for j in range(nA)
        }
        cancel = {i: solver.IntVar(0, 1, f"cancel_{i}") for i in range(nF)}

        # --- Constraints ---

        # 1. Coverage: assign to one aircraft OR cancel
        for i in range(nF):
            solver.Add(
                solver.Sum(x[i, j] for j in range(nA)) + cancel[i] == 1
            )

        # 2. AOG: unavailable aircraft cannot operate conflicting flights
        for j, a in enumerate(A):
            if a.is_aog:
                for i, f in enumerate(F):
                    if not a.is_available(f.sched_dep, f.sched_arr):
                        solver.Add(x[i, j] == 0)

        # 3. Conflict: no two time-overlapping flights on the same aircraft
        for j in range(nA):
            for i1 in range(nF):
                for i2 in range(i1 + 1, nF):
                    if self._conflicts(F[i1], F[i2]):
                        solver.Add(x[i1, j] + x[i2, j] <= 1)

        # --- Objective ---
        obj = solver.Objective()
        for i in range(nF):
            obj.SetCoefficient(cancel[i], Costs.CANCEL_FLIGHT)
        for i, f in enumerate(F):
            flight_cost = f.route_cost + f.arr_airport.airport_fee + Costs.DISPATCH_BASE
            for j in range(nA):
                obj.SetCoefficient(x[i, j], flight_cost)
        obj.SetMinimization()

        status = solver.Solve()
        if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            return self._failure()

        # --- Extract solution ---
        assignments = []
        for i, f in enumerate(F):
            for j, a in enumerate(A):
                if x[i, j].solution_value() > 0.5:
                    assignments.append({
                        "flight": f,
                        "aircraft": a,
                        "delay_mins": 0,
                    })

        cancelled_ids = [
            F[i].base_flight_id
            for i in range(nF)
            if cancel[i].solution_value() > 0.5
        ]

        # --- Cost breakdown ---
        cost_breakdown = {
            "route": sum(a["flight"].route_cost for a in assignments),
            "airport_fees": sum(a["flight"].arr_airport.airport_fee for a in assignments),
            "dispatch": len(assignments) * Costs.DISPATCH_BASE,
            "cancellations": len(cancelled_ids) * Costs.CANCEL_FLIGHT,
        }

        return {
            "status": "Success",
            "cost": solver.Objective().Value(),
            "assignments": assignments,
            "cancelled_flight_ids": cancelled_ids,
            "cost_breakdown": cost_breakdown,
        }

    @staticmethod
    def _failure() -> dict:
        return {
            "status": "Failed",
            "cost": float("inf"),
            "assignments": [],
            "cancelled_flight_ids": [],
            "cost_breakdown": {},
        }
