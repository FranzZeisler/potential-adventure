class Costs:
    DISPATCH_BASE = 5000.0
    CANCEL_FLIGHT = 50000.0
    CURFEW_VIOLATION = 50000.0
    EU261_PER_PAX = 250.0
    DEFAULT_PAX_PER_FLIGHT = 160
    SWAP_TAIL_PENALTY = 1500.0
    FERRY_FLIGHT_FLAT = 15000.0
    SUBCHARTER_BASE = 30000.0


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
