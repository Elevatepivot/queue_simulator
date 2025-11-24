import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from collections import deque

# ==========================================
# 1. CONFIGURATION
# ==========================================
st.set_page_config(page_title="HIA Strategic Planner V12", layout="wide")

# Constants
PAX_PROCESS_TIME_SEC = 24.0  
AVG_SPEND = 45.0             
MAX_WAIT_TOLERANCE = 15.0    
MIN_SHOPPING_TIME = 30.0     
AVG_PRE_FLIGHT_TIME = 90.0   
LANE_CAPACITY_HR = 3600 / PAX_PROCESS_TIME_SEC # 150 Pax/Hr
OPS_COST_HR = 150.0

# ==========================================
# 2. FIFO PHYSICS ENGINE
# ==========================================
def run_fifo_simulation(config, use_vip):
    
    minute_data = []
    passenger_data = []
    
    queue_std = deque()
    queue_vip = deque()
    
    cumulative_revenue = 0
    cumulative_lost = 0
    total_waits = [] 
    
    total_capacity_slots = 0
    used_capacity_slots = 0
    
    for t in range(180):
        hour_idx = t // 60
        settings = config[hour_idx]
        
        # 1. Inputs
        target_rate = settings['pax'] / 60.0
        actual_arrivals = np.random.poisson(target_rate)
        
        # 2. Add to Queue
        if use_vip:
            vip_count = int(actual_arrivals * 0.2)
            std_count = actual_arrivals - vip_count
            queue_vip.extend([t] * vip_count)
            queue_std.extend([t] * std_count)
        else:
            queue_std.extend([t] * actual_arrivals)

        # 3. Capacity Physics
        lanes = settings['lanes']
        if use_vip:
            vip_lanes = 2 if lanes > 4 else 1
            std_lanes = max(1, lanes - vip_lanes)
        else:
            vip_lanes = 0
            std_lanes = lanes
            
        cap_std_rate = (std_lanes * (3600 / PAX_PROCESS_TIME_SEC)) / 60.0
        cap_vip_rate = (vip_lanes * (3600 / PAX_PROCESS_TIME_SEC)) / 60.0
        
        total_capacity_slots += (cap_std_rate + cap_vip_rate)
        
        processed_std_count = int(cap_std_rate * np.random.uniform(0.95, 1.05))
        processed_vip_count = int(cap_vip_rate * np.random.uniform(0.95, 1.05)) if use_vip else 0

        # 4. Process Standard
        wait_times_this_min = []
        processed_this_min = 0
        
        for _ in range(processed_std_count):
            if queue_std:
                arrival_time = queue_std.popleft()
                wait = t - arrival_time
                wait_times_this_min.append(wait)
                total_waits.append(wait)
                processed_this_min += 1
                
                dwell_time = AVG_PRE_FLIGHT_TIME - wait - 10 
                
                if wait > MAX_WAIT_TOLERANCE:
                    sec_status = "Stressed"
                else:
                    sec_status = "Happy"
                    
                if dwell_time < MIN_SHOPPING_TIME:
                    ret_status = "Missed Opportunity"
                    cumulative_lost += AVG_SPEND
                else:
                    ret_status = "Shopper"
                    cumulative_revenue += AVG_SPEND
                
                if np.random.random() > 0.85:
                    passenger_data.append({
                        "Time": t, 
                        "Wait_Time": wait, 
                        "Security_Status": sec_status, 
                        "Retail_Status": ret_status,
                        "Dwell_Time": max(0, dwell_time)
                    })

        # 5. Process VIP
        for _ in range(processed_vip_count):
            if queue_vip:
                arrival_time = queue_vip.popleft()
                wait = t - arrival_time
                processed_this_min += 1
                total_waits.append(wait)
                cumulative_revenue += (AVG_SPEND * 3)

        used_capacity_slots += processed_this_min

        # 6. Logging
        avg_wait_now = np.mean(wait_times_this_min) if wait_times_this_min else 0
        
        minute_data.append({
            "Minute": t,
            "Hour": hour_idx + 1,
            "Arrivals": actual_arrivals * 60, 
            "Queue_Size": len(queue_std) + len(queue_vip),
            "Processed_Wait_Avg": avg_wait_now,
            "Capacity": (cap_std_rate + cap_vip_rate) * 60 
        })
        
    efficiency = (used_capacity_slots / total_capacity_slots) * 100 if total_capacity_slots > 0 else 0
        
    return pd.DataFrame(minute_data), pd.DataFrame(passenger_data), cumulative_revenue, cumulative_lost, total_waits, efficiency

# ==========================================
# 3. UI WITH CASCADING LOGIC
# ==========================================

st.title("✈️ HIA Strategic Operations Planner")

# Helper function to calculate and display guidance
def calculate_guidance(pax_input, lanes_input, previous_queue=0):
    # Effective Demand = New Arrivals + Backlog from previous hour
    total_demand = pax_input + previous_queue
    
    needed_exact = total_demand / LANE_CAPACITY_HR
    needed_lanes = int(np.ceil(needed_exact))
    
    # Calculate residual queue for next hour
    # Capacity = Lanes * 150
    capacity = lanes_input * LANE_CAPACITY_HR
    residual = max(0, total_demand - capacity)
    
    # Cost Waste Calculation
    current_cost = lanes_input * OPS_COST_HR
    optimal_cost = needed_lanes * OPS_COST_HR
    waste = current_cost - optimal_cost

    # Display Logic
    if lanes_input < needed_lanes:
        msg = f":red[**⚠️ Critical!** Need **{needed_lanes}** lanes]"
        if previous_queue > 0:
            msg += f" (Includes **{int(previous_queue)}** backlog!)"
        st.markdown(msg)
    elif lanes_input <= needed_lanes + 2:
        st.markdown(f":green[**✅ Optimal.** Efficient spend.]")
    else:
        st.markdown(f":orange[**💰 Over-staffed!** Waste: ${waste:,.0f}/hr]")
        st.caption(f"Reduce to ~{needed_lanes + 1} lanes.")
        
    return residual

# --- CASCADING INPUTS ---
with st.expander("⚙️ **Control Room Settings (Cascading Logic)**", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    scenario = []
    
    # --- HOUR 1 ---
    with c1:
        st.info("🕐 **08:00 - 09:00**")
        h1_p = st.number_input("Arrivals", 0, 6000, 2000, key="h1p")
        h1_l = st.slider("Lanes", 1, 30, 4, key="h1l") 
        # Calc H1 outcome to feed H2
        h1_residual = calculate_guidance(h1_p, h1_l, 0)
        scenario.append({'pax': h1_p, 'lanes': h1_l})
        
    # --- HOUR 2 ---
    with c2:
        st.warning("🕑 **09:00 - 10:00**")
        h2_p = st.number_input("Arrivals", 0, 6000, 3000, key="h2p") 
        h2_l = st.slider("Lanes", 1, 30, 15, key="h2l")
        # Calc H2 outcome to feed H3 (Input includes H1 residual)
        h2_residual = calculate_guidance(h2_p, h2_l, h1_residual) 
        scenario.append({'pax': h2_p, 'lanes': h2_l})
        
    # --- HOUR 3 ---
    with c3:
        st.success("🕒 **10:00 - 11:00**")
        h3_p = st.number_input("Arrivals", 0, 6000, 1000, key="h3p")
        h3_l = st.slider("Lanes", 1, 30, 12, key="h3l")
        # Calc H3 outcome (Input includes H2 residual)
        h3_residual = calculate_guidance(h3_p, h3_l, h2_residual) 
        scenario.append({'pax': h3_p, 'lanes': h3_l})
        
    with c4:
        st.markdown("##### Analysis Mode")
        use_vip = st.checkbox("VIP Fast Track")
        st.markdown("<br>", unsafe_allow_html=True) 
        if st.button("🚀 Run Simulation", type="primary", use_container_width=True):
            run = True
        else:
            run = True

if run:
    df_sys, df_pax, rev, lost, all_waits, efficiency = run_fifo_simulation(scenario, use_vip)

    # --- KPI ROW ---
    st.divider()
    k1, k2, k3, k4, k5 = st.columns(5)
    
    avg_wait_total = np.mean(all_waits) if all_waits else 0
    end_queue = df_sys['Queue_Size'].iloc[-1]
    
    k1.metric("Avg Wait Time", f"{avg_wait_total:.1f} min", 
              delta="Excellent" if avg_wait_total < 10 else "Slow", delta_color="inverse")
    
    k2.metric("Residual Queue", f"{int(end_queue)} pax", 
              delta="Clear" if end_queue < 50 else "Backlog", delta_color="inverse")
    
    k3.metric("Staff Efficiency", f"{efficiency:.1f}%", 
              help="Active time vs Idle time",
              delta="Wasteful" if efficiency < 50 else "Optimal")

    k4.metric("Projected Revenue", f"${rev:,.0f}", delta="Realized")
    k5.metric("Lost Opportunity", f"${lost:,.0f}", delta="Minimize", delta_color="inverse")

    # --- CHART 1: SUPPLY VS DEMAND ---
    st.subheader("1. Supply vs. Demand Physics")
    fig_main = go.Figure()
    
    fig_main.add_trace(go.Scatter(
        x=df_sys['Minute'], y=df_sys['Queue_Size'],
        mode='lines', name='Queue Size (Pax)',
        fill='tozeroy', line=dict(color='rgba(255, 75, 75, 0.5)', width=0),
        yaxis='y2'
    ))
    fig_main.add_trace(go.Scatter(
        x=df_sys['Minute'], y=df_sys['Capacity'],
        mode='lines', name='Capacity (Pax/Hr)',
        line=dict(color='#00CC96', width=3)
    ))
    fig_main.add_trace(go.Scatter(
        x=df_sys['Minute'], y=df_sys['Arrivals'],
        mode='lines', name='Arrival Rate (Pax/Hr)',
        line=dict(color='#636EFA', width=2)
    ))

    for x in [60, 120]:
        fig_main.add_vline(x=x, line_dash="dot", line_color="grey")

    fig_main.update_layout(
        height=400, margin=dict(l=0,r=0,t=0,b=0),
        yaxis=dict(title="Flow Rate (Pax/Hr)", side="left"),
        yaxis2=dict(title="Queue Depth (Pax)", overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig_main, use_container_width=True)

    # --- CHART 2: INDIVIDUAL SCATTER ---
    st.subheader("2. Individual Passenger Experience (Scatter)")
    
    if not df_pax.empty:
        color_map_sec = {"Happy": "#00CC96", "Stressed": "#FF4B4B"}
        
        fig_scatter = px.scatter(
            df_pax, x="Time", y="Wait_Time", color="Security_Status",
            color_discrete_map=color_map_sec,
            labels={"Wait_Time": "Wait (Min)", "Time": "Minute Cleared", "Security_Status": "Pax Mood"},
            title="Wait Time vs. Time Cleared"
        )
        
        fig_scatter.add_hline(
            y=MAX_WAIT_TOLERANCE, 
            line_dash="dash", 
            line_color="white", 
            line_width=2,
            annotation_text="Stress Threshold (15m)", 
            annotation_position="top left",
            annotation_font_color="white",
            annotation_font_size=14
        )
        
        fig_scatter.update_layout(
            height=350, 
            margin=dict(l=0,r=0,t=30,b=0),
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.warning("No passengers processed.")

    # --- CHART 3 & 4: COMMERCIAL IMPACT ---
    c_left, c_right = st.columns(2)
    
    with c_left:
        st.subheader("3. Average Wait Trend")
        fig_wait = go.Figure()
        fig_wait.add_trace(go.Scatter(
            x=df_sys['Minute'], y=df_sys['Processed_Wait_Avg'],
            mode='lines', name='Avg Wait',
            line=dict(color='#FFA500', width=3)
        ))
        fig_wait.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), yaxis=dict(title="Minutes"))
        st.plotly_chart(fig_wait, use_container_width=True)
        
    with c_right:
        st.subheader("4. Retail Opportunity (Dwell Time)")
        if not df_pax.empty:
            color_map_ret = {"Shopper": "#00CC96", "Missed Opportunity": "#FF4B4B"}
            
            fig_hist = px.histogram(df_pax, x="Dwell_Time", nbins=30,
                                    color="Retail_Status",
                                    color_discrete_map=color_map_ret,
                                    labels={"Dwell_Time": "Minutes Left to Shop", "Retail_Status": "Category"},
                                    title="Distribution of Shopping Time")
            
            fig_hist.add_vline(
                x=MIN_SHOPPING_TIME, 
                line_dash="dash", 
                line_color="white", 
                line_width=2,
                annotation_text="Min Shop Time (30m)",
                annotation_position="top right"
            )
            
            fig_hist.update_layout(
                height=300, 
                margin=dict(l=0,r=0,t=30,b=0),
                legend=dict(orientation="h", y=1.1)
            )
            st.plotly_chart(fig_hist, use_container_width=True)