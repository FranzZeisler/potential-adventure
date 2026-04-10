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
                              AIRPORT_OBJS, generate_mock_schedule,
                              generate_crew_roster, assign_crew_to_tails)

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="SunExpress Recovery Optimisation Dashboard",
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

# Initialize session state
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = generate_mock_schedule(sim_start, num_days=3)
if 'crew_roster' not in st.session_state:
    st.session_state.crew_roster = generate_crew_roster(sim_start)
if 'tail_crew' not in st.session_state:
    st.session_state.tail_crew = assign_crew_to_tails(st.session_state.crew_roster)
if 'last_result' not in st.session_state:
    st.session_state.last_result = None

df_schedule = st.session_state.schedule_df
all_tail_numbers = [
    reg for sublist in sunexpress_fleet.values() for reg in sublist
]

# Future flights for diversion selector
future_flights_df = df_schedule[
    (df_schedule['End'] > current_sim_time) &
    (~df_schedule['FlightNumber'].isin(["MAINT", "AOG"]))
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

disruption_type = st.sidebar.radio(
    "Disruption Type",
    ["AOG (Aircraft Grounded)", "Diversion (Flight Diverted)"]
)

if disruption_type == "AOG (Aircraft Grounded)":
    opt_tail = st.sidebar.selectbox("Select Aircraft (AOG)", all_tail_numbers)
    opt_start_time = st.sidebar.time_input("Grounding Start Time",
                                           current_sim_time.time())
    opt_duration = st.sidebar.slider("Grounding Duration (Hours)", 1, 24, 6)
    diversion_airport = None
    diversion_ground_delay = None
else:
    future_flt_nums = future_flights_df['FlightNumber'].unique().tolist()
    if not future_flt_nums:
        st.sidebar.warning("No future flights available for diversion.")
        st.stop()
    diverted_flight_num = st.sidebar.selectbox("Select Flight to Divert", future_flt_nums)
    diversion_airport = st.sidebar.selectbox(
        "Alternate Airport",
        [c for c in AIRPORT_OBJS.keys() if c not in ["AYT", "ADB", "SAW", "ESB"]] + ["LHR", "BCN", "FCO"]
    )
    diversion_ground_delay = st.sidebar.slider("Ground Delay at Alternate (Hours)", 1, 12, 3)
    diverted_row = future_flights_df[future_flights_df['FlightNumber'] == diverted_flight_num].iloc[0]
    opt_tail = diverted_row['Tail']
    opt_start_time = None
    opt_duration = None

if st.sidebar.button("Re-Optimise Schedule", type="primary"):

    if disruption_type == "AOG (Aircraft Grounded)":
        dis_start_dt = current_sim_time.replace(hour=opt_start_time.hour,
                                                minute=opt_start_time.minute)
        dis_end_dt = dis_start_dt + timedelta(hours=opt_duration)

        # Visually mark the AOG block on the Gantt chart
        new_aog_row = pd.DataFrame([{
            "Tail": opt_tail,
            "Aircraft": get_fleet_type(opt_tail),
            "FlightNumber": "AOG",
            "Departure": "SYS",
            "Arrival": "SYS",
            "Start": dis_start_dt,
            "End": dis_end_dt,
            "Status": "AOG / Maint",
            "Label": "⚠️ UNEXPECTED AOG",
            "Pax": 0,
            "RouteCost": 0.0,
            "AirportFee": 0.0,
        }])
        st.session_state.schedule_df = pd.concat(
            [st.session_state.schedule_df, new_aog_row], ignore_index=True)
    else:
        # Diversion: mark diverted flight and compute dis window
        dis_start_dt = diverted_row['End']
        dis_end_dt = dis_start_dt + timedelta(hours=diversion_ground_delay)

        idx_list = st.session_state.schedule_df.index[
            st.session_state.schedule_df['FlightNumber'] == diverted_flight_num
        ].tolist()
        if idx_list:
            i = idx_list[0]
            st.session_state.schedule_df.at[i, 'Status'] = "Diverted"
            st.session_state.schedule_df.at[i, 'Label'] = f"↪ DIVERTED -> {diversion_airport}"

    with st.spinner("Translating Data & Running Master Problem..."):

        # Build unique Airports
        all_locs = pd.concat([
            st.session_state.schedule_df['Departure'],
            st.session_state.schedule_df['Arrival']
        ]).unique()
        airports_dict = {
            loc: AIRPORT_OBJS.get(loc, Airport(code=loc))
            for loc in all_locs if loc not in ("BASE", "SYS")
        }

        # Build Aircraft Fleet with crew_ids
        fleet_objs = []
        for tail in all_tail_numbers:
            is_aog = (tail == opt_tail)
            crew_ids = st.session_state.tail_crew.get(tail, [])
            fleet_objs.append(
                Aircraft(tail_number=tail,
                         fleet_type=get_fleet_type(tail),
                         is_aog=is_aog,
                         aog_start=dis_start_dt if is_aog else None,
                         aog_end=dis_end_dt if is_aog else None,
                         crew_ids=crew_ids))

        # Build Flights
        flight_objs = []
        for _, row in st.session_state.schedule_df.iterrows():
            if row['FlightNumber'] in ["MAINT", "AOG"]:
                continue
            if row['End'] > current_sim_time:
                dep_apt = airports_dict.get(row['Departure'], Airport(code=row['Departure']))
                arr_apt = airports_dict.get(row['Arrival'], Airport(code=row['Arrival']))
                pax = int(row.get('Pax', 160)) if pd.notna(row.get('Pax', 160)) else 160
                rc = float(row.get('RouteCost', Costs.DEFAULT_ROUTE_COST)) if pd.notna(row.get('RouteCost', Costs.DEFAULT_ROUTE_COST)) else Costs.DEFAULT_ROUTE_COST
                f = Flight(flight_number=row['FlightNumber'],
                           dep_airport=dep_apt,
                           arr_airport=arr_apt,
                           sched_dep=row['Start'],
                           sched_arr=row['End'],
                           pax_count=pax,
                           route_cost=rc)
                flight_objs.append(f)

        # Execute Solver
        optimizer = RecoveryOptimizer(
            flights=flight_objs,
            aircraft_fleet=fleet_objs,
            crew_roster=st.session_state.crew_roster,
        )
        result = optimizer.run(max_iterations=10)
        st.session_state.last_result = result

    # Apply the Mathematical Results to the DataFrame
    if result["status"] == "Success":
        st.sidebar.success(
            f"Optimal Solution Found!\n**Total Cost:** €{result['cost']:,.0f}")
        st.sidebar.info(
            f"Generated {result['total_columns_generated']} dynamic rotations.")

        # Apply Cancellations
        cancelled_fids = result["cancelled_flight_ids"]
        for _, row in st.session_state.schedule_df.iterrows():
            fid = f"{row['FlightNumber']}_{row['Start'].strftime('%Y%m%d')}"
            if fid in cancelled_fids:
                idx = st.session_state.schedule_df.index[
                    st.session_state.schedule_df['FlightNumber'] ==
                    row['FlightNumber']].tolist()
                if idx:
                    st.session_state.schedule_df.at[idx[0], 'Status'] = "Cancelled"
                    st.session_state.schedule_df.at[idx[0], 'Label'] = f"❌ CANCELLED ({row['FlightNumber']})"

        # Apply New Tail Assignments and Delays
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
                    st.session_state.schedule_df.at[i, 'Label'] = f"🔄 SWAP {f.flight_number}"
                    swaps_made += 1

                if f.delay_mins > 0:
                    st.session_state.schedule_df.at[i, 'Start'] = f.sched_dep
                    st.session_state.schedule_df.at[i, 'End'] = f.sched_arr
                    st.session_state.schedule_df.at[i, 'Status'] = "Delayed"
                    st.session_state.schedule_df.at[i, 'Label'] = f"⏱ DELAY +{f.delay_mins}m {f.flight_number}"

        st.sidebar.warning(f"Reassigned {swaps_made} flights to different aircraft.")
        st.rerun()
    else:
        st.sidebar.error(
            "Solver failed to find a feasible solution. Constraints are too tight."
        )

# --- FILTER DATA ---
filtered_df = st.session_state.schedule_df[
    st.session_state.schedule_df['Aircraft'].isin(selected_ac_type)]
filtered_df = filtered_df[filtered_df['Status'].isin(selected_status)]

if search_query:
    search_query_upper = search_query.upper()
    filtered_df = filtered_df[
        filtered_df['Tail'].str.contains(search_query_upper) |
        filtered_df['FlightNumber'].str.contains(search_query_upper)
    ]

# Sort tails alphabetically for the Y-axis
filtered_df = filtered_df.sort_values(by="Tail", ascending=False)

# --- DASHBOARD HEADER ---
st.title("SunExpress Recovery Optimisation Dashboard")
st.markdown(
    "Dashboard simulating NetLine/Ops graphical fleet tracking. **Hover over flights for details.**"
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Aircraft", len(filtered_df['Tail'].unique()))
col2.metric("Total Flights", len(filtered_df))
cancelled_count = len(filtered_df[filtered_df['Status'] == "Cancelled"])
col3.metric("Cancelled", cancelled_count)
col4.metric("System Time", current_sim_time.strftime("%Y-%m-%d %H:%M UTC"))

# --- PLOTLY GANTT CHART ---
if not filtered_df.empty:

    num_tails = len(filtered_df['Tail'].unique())
    chart_height = max(600, num_tails * 25)

    hover_data = {
        "Start": "|%d %b %H:%M",
        "End": "|%d %b %H:%M",
        "Departure": True,
        "Arrival": True,
        "Status": True,
        "Aircraft": True,
        "Tail": False,
        "Label": False,
    }
    if 'Pax' in filtered_df.columns:
        hover_data["Pax"] = True

    fig = px.timeline(filtered_df,
                      x_start="Start",
                      x_end="End",
                      y="Tail",
                      color="Status",
                      color_discrete_map=STATUS_COLORS,
                      text="Label",
                      hover_name="FlightNumber",
                      hover_data=hover_data)

    fig.update_layout(
        template="plotly_dark",
        height=chart_height,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(
            title="",
            showgrid=True,
            gridcolor="#444",
            tickformat="%H:%M\n%d %b",
            side="top"
        ),
        yaxis=dict(
            title="",
            showgrid=True,
            gridcolor="#444",
            tickmode='linear',
            fixedrange=True
        ),
        legend=dict(orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1),
        font=dict(size=10))

    fig.update_traces(textfont=dict(color='white', size=9),
                      textposition='inside',
                      insidetextanchor='middle',
                      marker_line_color='rgb(0,0,0)',
                      marker_line_width=1.5,
                      opacity=0.9)

    fig.add_vline(x=current_sim_time,
                  line_width=2,
                  line_dash="dash",
                  line_color="red")

    st.plotly_chart(fig,
                    use_container_width=True,
                    config={'displayModeBar': False})

else:
    st.warning("No flights match your filter criteria.")

# --- RECOVERY PLAN COST BREAKDOWN ---
result = st.session_state.last_result
if result and result["status"] == "Success":
    st.markdown("---")
    st.subheader("📊 Recovery Plan - Cost Breakdown")

    # Aggregate cost breakdown across all rotations
    agg_costs: dict = {}
    for rot in result["rotations"]:
        for k, v in rot.cost_breakdown.items():
            agg_costs[k] = agg_costs.get(k, 0.0) + v

    n_cancelled = len(result["cancelled_flight_ids"])
    cancel_total = n_cancelled * Costs.CANCEL_FLIGHT
    if cancel_total > 0:
        agg_costs["cancellations"] = cancel_total

    # Summary metrics
    m1, m2, m3 = st.columns(3)
    delayed_count = sum(1 for rot in result["rotations"] for f in rot.flights if f.delay_mins > 0)
    swaps_count = 0
    for rot in result["rotations"]:
        orig_tails = st.session_state.schedule_df.set_index('FlightNumber')['Tail'].to_dict()
        for f in rot.flights:
            if orig_tails.get(f.flight_number) != rot.aircraft.tail_number:
                swaps_count += 1
    m1.metric("✈️ Cancelled Flights", n_cancelled)
    m2.metric("⏱️ Delayed Flights", delayed_count)
    m3.metric("🔄 Tail Swaps", swaps_count)

    # Bar chart of costs
    cost_df = pd.DataFrame(
        list(agg_costs.items()), columns=["Category", "Cost (€)"]
    ).sort_values("Cost (€)", ascending=False)

    fig_cost = px.bar(
        cost_df, x="Category", y="Cost (€)",
        title="Recovery Cost by Category",
        color="Category",
        template="plotly_dark",
        text_auto=".3s"
    )
    fig_cost.update_layout(showlegend=False, height=350)
    st.plotly_chart(fig_cost, use_container_width=True)

    # Recovery actions table
    actions = []
    for rot in result["rotations"]:
        for f in rot.flights:
            action = "Delayed" if f.delay_mins > 0 else "Scheduled"
            orig_tails = st.session_state.schedule_df.set_index('FlightNumber')['Tail'].to_dict()
            if orig_tails.get(f.flight_number) != rot.aircraft.tail_number:
                action = "Swapped"
            actions.append({
                "Flight": f.flight_number,
                "Action": action,
                "New Tail": rot.aircraft.tail_number,
                "Delay (min)": f.delay_mins,
                "EU261 (€)": f"{f.eu261_compensation:,.0f}",
                "Total Cost (€)": f"{rot.cost:,.0f}",
            })
    for fid in result["cancelled_flight_ids"]:
        flt_num = fid.rsplit("_", 1)[0]
        actions.append({
            "Flight": flt_num,
            "Action": "Cancelled",
            "New Tail": "-",
            "Delay (min)": 0,
            "EU261 (€)": "-",
            "Total Cost (€)": f"{Costs.CANCEL_FLIGHT:,.0f}",
        })

    if actions:
        st.dataframe(pd.DataFrame(actions), use_container_width=True, hide_index=True)
