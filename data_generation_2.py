"""
data_generation_2.py — Small domestic-Turkey dataset for debugging.

6 Boeing 737-800 tails operating on Turkish domestic routes only.
Single-day schedule, ~3-5 flights per aircraft.
"""
import streamlit as st
import pandas as pd
from datetime import timedelta, datetime
import random

from domain.airport import Airport
from domain.crew import CrewMember
from config import Costs

# ---------------------------------------------------------------------------
# Fleet — 6 aircraft only
# ---------------------------------------------------------------------------
sunexpress_fleet = {
    "Boeing 737-800": [
        "TC-SEA", "TC-SEB", "TC-SEC", "TC-SED", "TC-SEE", "TC-SEF",
    ],
}

# ---------------------------------------------------------------------------
# Airports — all within Turkey, no night curfews on domestic routes
# ---------------------------------------------------------------------------
AIRPORT_OBJS = {
    "SAW": Airport("SAW", min_turnaround_mins=45, curfew_start_hr=None, curfew_end_hr=None,
                   airport_fee=Costs.AIRPORT_FEES.get("SAW", 450.0)),
    "AYT": Airport("AYT", min_turnaround_mins=45, curfew_start_hr=None, curfew_end_hr=None,
                   airport_fee=Costs.AIRPORT_FEES.get("AYT", 400.0)),
    "ADB": Airport("ADB", min_turnaround_mins=45, curfew_start_hr=None, curfew_end_hr=None,
                   airport_fee=Costs.AIRPORT_FEES.get("ADB", 380.0)),
    "ESB": Airport("ESB", min_turnaround_mins=45, curfew_start_hr=None, curfew_end_hr=None,
                   airport_fee=Costs.AIRPORT_FEES.get("ESB", 390.0)),
    "ADA": Airport("ADA", min_turnaround_mins=40, curfew_start_hr=None, curfew_end_hr=None,
                   airport_fee=500.0),
    "TZX": Airport("TZX", min_turnaround_mins=40, curfew_start_hr=None, curfew_end_hr=None,
                   airport_fee=480.0),
}

HUBS = ["SAW", "AYT", "ADB", "ESB"]
DESTINATIONS = ["ADA", "TZX"]

# ---------------------------------------------------------------------------
# Route durations (hours) between each pair
# ---------------------------------------------------------------------------
_DURATIONS: dict = {
    ("SAW", "AYT"): 1.5, ("AYT", "SAW"): 1.5,
    ("SAW", "ADB"): 1.0, ("ADB", "SAW"): 1.0,
    ("SAW", "ESB"): 0.75, ("ESB", "SAW"): 0.75,
    ("SAW", "ADA"): 1.5, ("ADA", "SAW"): 1.5,
    ("SAW", "TZX"): 2.0, ("TZX", "SAW"): 2.0,
    ("AYT", "ESB"): 1.5, ("ESB", "AYT"): 1.5,
    ("AYT", "ADB"): 1.0, ("ADB", "AYT"): 1.0,
    ("ADB", "ADA"): 1.5, ("ADA", "ADB"): 1.5,
    ("ADB", "ESB"): 1.25, ("ESB", "ADB"): 1.25,
    ("ADA", "ESB"): 1.0, ("ESB", "ADA"): 1.0,
}

_ROUTE_COSTS: dict = {
    "SAW": 2800.0, "AYT": 3000.0, "ADB": 2800.0,
    "ESB": 2500.0, "ADA": 3500.0, "TZX": 4000.0,
}

DELAY_REASONS = [
    "Technical", "Weather", "ATC", "Late Crew", "Late Aircraft",
    "Passenger Issue", "Fuel Delay", "Ground Handling",
]

STATUS_COLORS = {
    "Scheduled": "#3498db",
    "Boarding": "#f1c40f",
    "Airborne": "#2ecc71",
    "Arrived": "#95a5a6",
    "Delayed": "#e67e22",
    "Cancelled": "#2c3e50",
    "AOG / Maint": "#e74c3c",
    "Diverted": "#9b59b6",
    "Available": "#1e3a4a",
}

_ALL_AIRPORTS = list(AIRPORT_OBJS.keys())


def _duration(dep: str, arr: str) -> float:
    return _DURATIONS.get((dep, arr), 1.5)


# ---------------------------------------------------------------------------
# Schedule generator
# ---------------------------------------------------------------------------
@st.cache_data
def generate_mock_schedule(start_date: datetime, num_days: int = 1) -> pd.DataFrame:
    random.seed(42)
    schedule = []
    sim_end = start_date + timedelta(days=num_days)
    # Global counter so every flight number is unique across all tails
    global_counter = 100

    for ac_type, tails in sunexpress_fleet.items():
        for tail in tails:
            current_loc = random.choice(HUBS)
            current_time = start_date + timedelta(hours=random.uniform(6, 8))
            flights_today = 0

            while current_time < sim_end and flights_today < 5:
                # Alternate between domestic destinations and hubs
                if current_loc in HUBS:
                    candidates = [loc for loc in _ALL_AIRPORTS if loc != current_loc]
                else:
                    candidates = HUBS

                next_loc = random.choice(candidates)
                dur = _duration(current_loc, next_loc)
                start_flight = current_time
                end_flight = start_flight + timedelta(hours=dur)

                if end_flight > sim_end:
                    break

                flt_num = f"XQ{global_counter}"
                global_counter += 1
                pax = random.randint(100, 189)
                route_cost = _ROUTE_COSTS.get(next_loc, 3000.0)
                airport_fee = AIRPORT_OBJS.get(next_loc, Airport(next_loc)).airport_fee

                schedule.append({
                    "Tail": tail,
                    "Aircraft": ac_type,
                    "FlightNumber": flt_num,
                    "Departure": current_loc,
                    "Arrival": next_loc,
                    "Start": start_flight,
                    "End": end_flight,
                    "Status": "Scheduled",
                    "Label": f"{flt_num} {current_loc}-{next_loc}",
                    "Pax": pax,
                    "RouteCost": route_cost,
                    "AirportFee": airport_fee,
                })

                current_time = end_flight + timedelta(minutes=45)
                current_loc = next_loc
                flights_today += 1

    return pd.DataFrame(schedule)


# ---------------------------------------------------------------------------
# Crew helpers (unchanged API)
# ---------------------------------------------------------------------------
def generate_crew_roster(sim_start: datetime, seed: int = 42) -> dict:
    random.seed(seed)
    roster = {}
    for ac_type, tails in sunexpress_fleet.items():
        for tail in tails:
            for role, prefix in [("Captain", "CPT"), ("First Officer", "FO")]:
                emp_id = f"{prefix}-{tail}"
                duty_start = sim_start + timedelta(hours=random.uniform(0, 6))
                crew = CrewMember(
                    employee_id=emp_id,
                    name=f"{role} {tail}",
                    role=role,
                    type_ratings={ac_type},
                    duty_start=duty_start,
                )
                roster[emp_id] = crew
    return roster


def assign_crew_to_tails(roster: dict) -> dict:
    tail_crew: dict = {}
    for emp_id in roster:
        tail = emp_id.split("-", 1)[1]
        tail_crew.setdefault(tail, []).append(emp_id)
    return tail_crew
