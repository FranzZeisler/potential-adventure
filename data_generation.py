import streamlit as st
import pandas as pd
from datetime import timedelta
import random

# Import the Airport class to use its business logic during generation
from domain.airport import Airport

# --- FLEET DATA ---
sunexpress_fleet = {
    "Boeing 737-800": [
        "TC-SEA", "TC-SEB", "TC-SEC", "TC-SED", "TC-SEE", "TC-SEF", "TC-SEG",
        "TC-SEH", "TC-SEI", "TC-SEJ", "TC-SEK", "TC-SEM", "TC-SEN", "TC-SEO",
        "TC-SEP", "TC-SER", "TC-SES", "TC-SET", "TC-SEU", "TC-SEV", "TC-SEX",
        "TC-SEY", "TC-SEZ", "TC-SNN", "TC-SNO", "TC-SNP", "TC-SNR", "TC-SNS",
        "TC-SNT", "TC-SNU", "TC-SNV", "TC-SNY", "TC-SNZ", "TC-SOA", "TC-SOB",
        "TC-SOC", "TC-SOD", "TC-SOE", "TC-SOF", "TC-SOG", "TC-SOH", "TC-SOI",
        "TC-SOJ", "TC-SOK", "TC-SOL", "TC-SOM", "TC-SON", "TC-SOO", "TC-SOP",
        "TC-SOR", "TC-SOY", "TC-SPA", "TC-SPB", "TC-SPC", "TC-SPD", "TC-SPE",
        "TC-SPF", "TC-SPH", "TC-SPI", "TC-SPJ", "TC-SPK", "TC-SPM", "TC-SPN",
        "TC-SPO", "TC-SPP", "TC-SPR", "TC-SPS", "TC-SPT", "TC-SPU", "TC-SPV",
        "TC-SPY", "TC-SRB"
    ],
    "Boeing 737 MAX 8": [
        "TC-SLA", "TC-SLB", "TC-SLC", "TC-SLD", "TC-SLE", "TC-SLF", "TC-SMA",
        "TC-SMB", "TC-SMC", "TC-SMD", "TC-SME", "TC-SMF", "TC-SMG", "TC-SMH",
        "TC-SMI", "TC-SMJ", "TC-SMK", "TC-SML", "TC-SMM", "TC-SMN", "TC-SMS",
        "TC-SMV", "TC-SMZ"
    ],
    "Reserve Aircraft": ["TC-RES1"],
    "Subcharter": ["WET-LEASE-1"]
}

# Define Airport Objects to access their curfew/turnaround logic
AIRPORT_OBJS = {
    # Hubs
    "AYT": Airport("AYT", min_turnaround_mins=45),
    "ADB": Airport("ADB", min_turnaround_mins=45),
    "SAW": Airport("SAW", min_turnaround_mins=50),
    "ESB": Airport("ESB", min_turnaround_mins=45),
    # Destinations (Many European airports have strict night curfews)
    "FRA": Airport("FRA", curfew_start_hr=23, curfew_end_hr=5),
    "MUC": Airport("MUC", curfew_start_hr=23, curfew_end_hr=6),
    "ZRH": Airport("ZRH", curfew_start_hr=23, curfew_end_hr=6),
    "CDG": Airport("CDG", curfew_start_hr=0, curfew_end_hr=5),
    "DUS": Airport("DUS"),
    "CGN": Airport("CGN"),
    "BER": Airport("BER"),
    "STR": Airport("STR"),
    "HAJ": Airport("HAJ"),
    "MAN": Airport("MAN"),
    "LGW": Airport("LGW"),
    "VIE": Airport("VIE"),
    "AMS": Airport("AMS")
}

HUBS = ["AYT", "ADB", "SAW", "ESB"]
DESTINATIONS = [code for code in AIRPORT_OBJS.keys() if code not in HUBS]

ROUTE_DURATIONS = {
    "FRA": 3.5,
    "MUC": 3.0,
    "DUS": 3.6,
    "CGN": 3.5,
    "BER": 3.2,
    "STR": 3.1,
    "HAJ": 3.4,
    "MAN": 4.5,
    "LGW": 4.2,
    "VIE": 2.5,
    "ZRH": 3.0,
    "CDG": 3.8,
    "AMS": 4.0
}

STATUS_COLORS = {
    "Scheduled": "#3498db",
    "Boarding": "#f1c40f",
    "Airborne": "#2ecc71",
    "Arrived": "#95a5a6",
    "Delayed": "#e67e22",
    "Cancelled": "#2c3e50",
    "AOG / Maint": "#e74c3c"
}


@st.cache_data
def generate_mock_schedule(start_date, num_days=2):
    schedule = []

    for ac_type, tails in sunexpress_fleet.items():
        if ac_type in ["Reserve Aircraft", "Subcharter"]:
            continue

        for tail in tails:
            # Random starting hub
            current_loc = random.choice(HUBS)
            # Start at a legal time (not in curfew)
            current_time = start_date + timedelta(hours=random.uniform(6, 8))

            end_schedule_time = start_date + timedelta(days=num_days)
            flight_counter = random.randint(100, 999)

            while current_time < end_schedule_time:
                # 1. Determine next destination
                next_loc = random.choice(
                    DESTINATIONS) if current_loc in HUBS else random.choice(
                        HUBS)

                # 2. Check Curfew at Departure
                dep_apt = AIRPORT_OBJS.get(current_loc, Airport(current_loc))
                while dep_apt.is_curfew_violated(current_time):
                    current_time += timedelta(
                        minutes=30)  # Wait until curfew ends

                # 3. Calculate Flight Times
                duration = ROUTE_DURATIONS.get(
                    next_loc if current_loc in HUBS else current_loc, 3.5)
                start_flight = current_time
                end_flight = start_flight + timedelta(hours=duration)

                # 4. Check Curfew at Arrival
                arr_apt = AIRPORT_OBJS.get(next_loc, Airport(next_loc))
                if arr_apt.is_curfew_violated(end_flight):
                    # If we would land in curfew, push the whole flight back to land after curfew
                    # This is how real schedulers avoid fines
                    current_time += timedelta(hours=1)
                    continue  # Retry this leg with the new start time

                # 5. Commit Flight
                flt_num = f"XQ{flight_counter}"
                schedule.append({
                    "Tail": tail,
                    "Aircraft": ac_type,
                    "FlightNumber": flt_num,
                    "Departure": current_loc,
                    "Arrival": next_loc,
                    "Start": start_flight,
                    "End": end_flight,
                    "Status": "Scheduled",
                    "Label": f"{flt_num} {current_loc}-{next_loc}"
                })

                # 6. Apply MIN TURNAROUND for next leg
                turnaround = timedelta(minutes=dep_apt.min_turnaround_mins)
                current_time = end_flight + turnaround
                current_loc = next_loc
                flight_counter += 1

    return pd.DataFrame(schedule)
