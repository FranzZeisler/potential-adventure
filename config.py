class Costs:
    DISPATCH_BASE = 5000.0
    CANCEL_FLIGHT = 50000.0
    CURFEW_VIOLATION = 50000.0
    EU261_PER_PAX = 250.0
    DEFAULT_PAX_PER_FLIGHT = 160
    SWAP_TAIL_PENALTY = 1500.0
    FERRY_FLIGHT_FLAT = 15000.0
    SUBCHARTER_BASE = 30000.0
    RESERVE_AIRCRAFT_COST = 20000.0
    DELAY_COST_PER_MIN = 85.0
    TYPE_CERT_CREW_SWAP = 8000.0
    DEFAULT_ROUTE_COST = 8000.0
    DEFAULT_AIRPORT_FEE = 500.0

    ROUTE_COSTS = {
        "FRA": 9500.0, "MUC": 8800.0, "DUS": 9200.0, "CGN": 9000.0,
        "BER": 8500.0, "STR": 8300.0, "HAJ": 8700.0, "MAN": 11000.0,
        "LGW": 10500.0, "VIE": 7500.0, "ZRH": 8800.0, "CDG": 9800.0, "AMS": 10200.0,
    }

    AIRPORT_FEES = {
        "FRA": 1800.0, "MUC": 1600.0, "DUS": 1200.0, "CGN": 1000.0,
        "BER": 1100.0, "STR": 900.0, "HAJ": 950.0, "MAN": 1400.0,
        "LGW": 1700.0, "VIE": 1300.0, "ZRH": 1900.0, "CDG": 2000.0,
        "AMS": 1500.0, "AYT": 400.0, "ADB": 380.0, "SAW": 450.0, "ESB": 390.0,
    }


class OpsRules:
    """Standard operational time limits and physical constraints."""

    # Ground constraints
    MIN_TURNAROUND_MINS = 45  # Minimum time an aircraft needs on the ground

    # Standard Airport Curfew (can be overridden by specific Airport instances)
    DEFAULT_CURFEW_START = 23  # 11:00 PM
    DEFAULT_CURFEW_END = 5  # 05:00 AM


class SolverSettings:
    """Tuning parameters for the Google OR-Tools meta-algorithm."""

    MAX_FLIGHTS_PER_ROTATION = 3  # DFS depth-limit for our Pricing Sub-Problem heuristic
    REDUCED_COST_THRESHOLD = -0.01  # Float tolerance for negative reduced costs
    MAX_ITERATIONS = 15  # Failsafe to prevent the while-loop from running forever
