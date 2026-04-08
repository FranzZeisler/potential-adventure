import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- NEW IMPORTS: Column Generation and Domain Models ---
from column_generation import RecoveryOptimizer
from domain.airport import Airport
from domain.aircraft import Aircraft
from domain.flight import Flight
from config import Costs

# Import configuration and data generation logic
from data_generation import (sunexpress_fleet, STATUS_COLORS, DELAY_REASONS,
                             generate_mock_schedule)

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="SunExpress Ops Control",
                   page_icon="✈️",
                   layout="wide",
                   initial_sidebar_state="expanded")


# --- HELPER FUNCTION ---
def get_fleet_type(tail):
    """Helper to find the aircraft type string for a given tail number."""
    for ac_type, tails in sunexpress_fleet.items():
        if tail in tails:
            return ac_type
    return "Unknown"


# --- MAIN APP LOGIC ---

# Base simulation date (Yesterday to tomorrow for a good spread)
sim_start = datetime.now().replace(hour=0, minute=0, second=0,
                                   microsecond=0) - timedelta(days=1)
current_sim_time = sim_start + timedelta(hours=24)

# Initialize session state for the schedule dataframe so we can mutate it
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = generate_mock_schedule(sim_start, num_days=3)

df_schedule = st.session_state.schedule_df
all_tail_numbers = [
    reg for sublist in sunexpress_fleet.values() for reg in sublist
]

# --- SIDEBAR: FILTERS ---
st.sidebar.image(
    "https://upload.wikimedia.org/wikipedia/commons/thumb/1/17/SunExpress_Logo.svg/1024px-SunExpress_Logo.svg.png",
    width=200)
st.sidebar.markdown("### Operations Control")

selected_ac_type = st.sidebar.multiselect("Aircraft Type",
                                          options=list(sunexpress_fleet.keys()),
                                          default=list(sunexpress_fleet.keys()))

selected_status = st.sidebar.multiselect("Flight Status",
                                         options=list(STATUS_COLORS.keys()),
                                         default=list(STATUS_COLORS.keys()))

# Search by Tail or Flight Number
search_query = st.sidebar.text_input("Search Tail / Flight No.", "")

# --- SIDEBAR: ENTERPRISE OPTIMIZER ---
st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Time-Space TSN Optimizer")

# Inputs for the disruption event
opt_tail = st.sidebar.selectbox("Select Aircraft (AOG)", all_tail_numbers)
opt_start_time = st.sidebar.time_input("Grounding Start Time",
                                       current_sim_time.time())
opt_duration = st.sidebar.slider("Grounding Duration (Hours)", 1, 24, 6)

if st.sidebar.button("Run Column Generation", type="primary"):

    # 1. Define the disruption window mathematically
    dis_start_dt = current_sim_time.replace(hour=opt_start_time.hour,
                                            minute=opt_start_time.minute)
    dis_end_dt = dis_start_dt + timedelta(hours=opt_duration)

    # Visually mark the AOG block on the Gantt chart first
    new_aog_row = pd.DataFrame([{
        "Tail": opt_tail,
        "Aircraft": get_fleet_type(opt_tail),
        "FlightNumber": "AOG",
        "Departure": "SYS",
        "Arrival": "SYS",
        "Start": dis_start_dt,
        "End": dis_end_dt,
        "Status": "AOG / Maint",
        "Label": "⚠️ UNEXPECTED AOG"
    }])
    st.session_state.schedule_df = pd.concat(
        [st.session_state.schedule_df, new_aog_row], ignore_index=True)

    with st.spinner("Translating Data & Running Master Problem..."):

        # --- ADAPTER STEP 1: Translate DataFrame to OOP Models ---

        # Build unique Airports
        all_locs = pd.concat([
            st.session_state.schedule_df['Departure'],
            st.session_state.schedule_df['Arrival']
        ]).unique()
        airports_dict = {
            loc: Airport(code=loc) for loc in all_locs if loc != "BASE"
        }

        # Build Aircraft Fleet
        fleet_objs = []
        for tail in all_tail_numbers:
            is_aog = (tail == opt_tail)
            fleet_objs.append(
                Aircraft(tail_number=tail,
                         fleet_type=get_fleet_type(tail),
                         is_aog=is_aog,
                         aog_start=dis_start_dt if is_aog else None,
                         aog_end=dis_end_dt if is_aog else None))

        # Build Flights
        flight_objs = []
        for _, row in st.session_state.schedule_df.iterrows():
            if row['FlightNumber'] in ["MAINT", "AOG"]:
                continue

            # Only pass future flights to the optimizer to save compute time
            if row['End'] > current_sim_time:
                f = Flight(flight_number=row['FlightNumber'],
                           dep_airport=airports_dict.get(
                               row['Departure'],
                               Airport(code=row['Departure'])),
                           arr_airport=airports_dict.get(
                               row['Arrival'], Airport(code=row['Arrival'])),
                           sched_dep=row['Start'],
                           sched_arr=row['End'])
                flight_objs.append(f)

        # --- ADAPTER STEP 2: Execute Solver ---
        optimizer = RecoveryOptimizer(flights=flight_objs,
                                      aircraft_fleet=fleet_objs)
        result = optimizer.run(max_iterations=10)

    # --- ADAPTER STEP 3: Apply the Mathematical Results to the DataFrame ---
    if result["status"] == "Success":
        st.sidebar.success(
            f"Optimal Solution Found!\n**Total Cost:** €{result['cost']:,.0f}")
        st.sidebar.info(
            f"Generated {result['total_columns_generated']} dynamic rotations.")

        # Apply Cancellations
        cancelled_fids = result["cancelled_flight_ids"]
        for _, row in st.session_state.schedule_df.iterrows():
            # Match the generated ID format from flight.py
            fid = f"{row['FlightNumber']}_{row['Start'].strftime('%Y%m%d')}"

            if fid in cancelled_fids:
                idx = st.session_state.schedule_df.index[
                    st.session_state.schedule_df['FlightNumber'] ==
                    row['FlightNumber']].tolist()
                if idx:
                    st.session_state.schedule_df.at[idx[0],
                                                    'Status'] = "Cancelled"
                    st.session_state.schedule_df.at[
                        idx[0],
                        'Label'] = f"❌ CANCELLED ({row['FlightNumber']})"

        # Apply New Tail Assignments (Swaps)
        swaps_made = 0
        for rot in result["rotations"]:
            for f in rot.flights:
                idx = st.session_state.schedule_df.index[
                    st.session_state.schedule_df['FlightNumber'] ==
                    f.flight_number].tolist()
                if not idx:
                    continue
                i = idx[0]

                old_tail = st.session_state.schedule_df.at[i, 'Tail']
                new_tail = rot.aircraft.tail_number

                if old_tail != new_tail:
                    st.session_state.schedule_df.at[i, 'Tail'] = new_tail
                    st.session_state.schedule_df.at[
                        i, 'Label'] = f"🔄 SWAP {f.flight_number}"
                    swaps_made += 1

        st.sidebar.warning(
            f"Reassigned {swaps_made} flights to different aircraft.")
        st.rerun()  # Force UI refresh to show updated Gantt chart

    else:
        st.sidebar.error(
            "Solver failed to find a feasible solution. Constraints are too tight."
        )

# --- FILTER DATA ---
filtered_df = st.session_state.schedule_df[
    st.session_state.schedule_df['Aircraft'].isin(selected_ac_type)]
filtered_df = filtered_df[filtered_df['Status'].isin(selected_status)]

if search_query:
    search_query = search_query.upper()
    filtered_df = filtered_df[filtered_df['Tail'].str.contains(search_query) |
                              filtered_df['FlightNumber'].str.
                              contains(search_query)]

# Sort tails alphabetically for the Y-axis
filtered_df = filtered_df.sort_values(by="Tail", ascending=False)

# --- DASHBOARD HEADER ---
st.title("Gantt: Fleet Assignment & Movement")
st.markdown(
    "Dashboard simulating NetLine/Ops graphical fleet tracking. **Hover over flights for details.**"
)

col1, col2, col3 = st.columns(3)
col1.metric("Active Aircraft", len(filtered_df['Tail'].unique()))
col2.metric("Total Flights Visualized", len(filtered_df))
col3.metric("System Time", current_sim_time.strftime("%Y-%m-%d %H:%M UTC"))

# --- PLOTLY GANTT CHART ---
if not filtered_df.empty:

    # Calculate dynamic height based on number of distinct aircraft (so rows don't get squished)
    num_tails = len(filtered_df['Tail'].unique())
    chart_height = max(600, num_tails * 25)  # 25 pixels per aircraft row

    fig = px.timeline(filtered_df,
                      x_start="Start",
                      x_end="End",
                      y="Tail",
                      color="Status",
                      color_discrete_map=STATUS_COLORS,
                      text="Label",
                      hover_name="FlightNumber",
                      hover_data={
                          "Start": "|%d %b %H:%M",
                          "End": "|%d %b %H:%M",
                          "Departure": True,
                          "Arrival": True,
                          "Status": True,
                          "Aircraft": True,
                          "Tail": False,
                          "Label": False
                      })

    # NetLine specific visual styling
    fig.update_layout(
        template="plotly_dark",
        height=chart_height,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(
            title="",
            showgrid=True,
            gridcolor="#444",
            tickformat="%H:%M\n%d %b",
            side="top"  # Put time axis at the top like aviation software
        ),
        yaxis=dict(
            title="",
            showgrid=True,
            gridcolor="#444",
            tickmode='linear',
            fixedrange=True  # Prevents Y-axis zooming to keep tails aligned
        ),
        legend=dict(orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1),
        font=dict(size=10))

    # Style the bars and text
    fig.update_traces(textfont=dict(color='white', size=9),
                      textposition='inside',
                      insidetextanchor='middle',
                      marker_line_color='rgb(0,0,0)',
                      marker_line_width=1.5,
                      opacity=0.9)

    # Add a "Current Time" vertical line
    fig.add_vline(x=current_sim_time,
                  line_width=2,
                  line_dash="dash",
                  line_color="red")

    # Render in Streamlit
    st.plotly_chart(fig,
                    use_container_width=True,
                    config={'displayModeBar': False})

else:
    st.warning("No flights match your filter criteria.")
