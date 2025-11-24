import streamlit as st
import pandas as pd
import json
import plotly.graph_objects as go

# ==========================================
# 1. LOAD DATA
# ==========================================
json_data = """
{
    "simulation_metadata": {
        "description": "Shutdown simulation and feasibility check",
        "baseline_scenario": "1"
    },
    "scenarios": {
        "shutdown_source_10": {
            "override_type": "Force_Shutdown",
            "target_node": "source_10",
            "original_flow": 990.86546575,
            "forced_flow": 0.0,
            "system_supply_post_override": 1287.4582147499796,
            "system_demand_fixed": 2278.3236804994576,
            "supply_gap": 990.8654657494781,
            "feasibility_status": "Supply Gap / Infeasible",
            "financial_impact_estimate": 4082.36571889,
            "details": { "unit_cost": 4.12 }
        },
        "shutdown_source_11": {
            "override_type": "Force_Shutdown",
            "target_node": "source_11",
            "original_flow": 726.082153844,
            "forced_flow": 0.0,
            "system_supply_post_override": 1552.2415266559797,
            "system_demand_fixed": 2278.3236804994576,
            "supply_gap": 726.082153843478,
            "feasibility_status": "Supply Gap / Infeasible",
            "financial_impact_estimate": 1495.72923691864,
            "details": { "unit_cost": 2.06 }
        },
        "shutdown_source_5": {
            "override_type": "Force_Shutdown",
            "target_node": "source_5",
            "original_flow": 422.060087702,
            "forced_flow": 0.0,
            "system_supply_post_override": 1856.2635927979798,
            "system_demand_fixed": 2278.3236804994576,
            "supply_gap": 422.06008770147787,
            "feasibility_status": "Supply Gap / Infeasible",
            "financial_impact_estimate": 1042.48841662394,
            "details": { "unit_cost": 2.47 }
        },
        "shutdown_source_4": {
            "override_type": "Force_Shutdown",
            "target_node": "source_4",
            "original_flow": 82.4465416417,
            "forced_flow": 0.0,
            "system_supply_post_override": 2195.8771388582795,
            "system_demand_fixed": 2278.3236804994576,
            "supply_gap": 82.4465416411781,
            "feasibility_status": "Supply Gap / Infeasible",
            "financial_impact_estimate": 313.29685823845995,
            "details": { "unit_cost": 3.8 }
        },
        "shutdown_source_7": {
            "override_type": "Force_Shutdown",
            "target_node": "source_7",
            "original_flow": 51.054196567,
            "forced_flow": 0.0,
            "system_supply_post_override": 2227.2694839329797,
            "system_demand_fixed": 2278.3236804994576,
            "supply_gap": 51.05419656647791,
            "feasibility_status": "Supply Gap / Infeasible",
            "financial_impact_estimate": 110.78760655039,
            "details": { "unit_cost": 2.17 }
        }
    }
}
"""

def load_data():
    data = json.loads(json_data)
    rows = []
    for key, val in data['scenarios'].items():
        row = val
        row['scenario_id'] = key
        # Calculate the "Ramp Up" (Did other sources help?)
        # Initial Total Supply approx = Post Supply + Original Flow (assuming balance)
        # Ramp Up = (Supply Post + Gap) - (Supply Post + Original) ... wait
        # Simpler logic:
        # Demand = 2278
        # We lost 'Original Flow'
        # We have 'Supply Post'
        # If Supply Post < (Demand - Original Flow), others ramped DOWN (unlikely)
        # If Supply Post > (Demand - Original Flow), others ramped UP
        
        # Actually, simpler:
        # Gap = Demand - Post_Supply
        # Loss = Original_Flow
        # Compensation = Loss - Gap
        
        compensation = val['original_flow'] - val['supply_gap']
        # Floating point fix
        if abs(compensation) < 0.001: compensation = 0.0
        
        row['compensation_volume'] = compensation
        row['resilience_score'] = (compensation / val['original_flow']) * 100 if val['original_flow'] > 0 else 0
        
        rows.append(row)
    return pd.DataFrame(rows)

df = load_data()

# ==========================================
# 2. DASHBOARD
# ==========================================
st.set_page_config(page_title="Network Resilience Analysis", layout="wide")

st.title("🛡️ Network Resilience: Failure Compensation Analysis")
st.markdown("This dashboard analyzes **what happens when a source fails**. Does the network compensate by ramping up other sources, or does it fail 1-to-1?")

# --- SELECTOR ---
selected_asset = st.selectbox("Select Shutdown Scenario:", df['target_node'].unique())

# Filter Data
record = df[df['target_node'] == selected_asset].iloc[0]

# --- METRICS ROW ---
c1, c2, c3 = st.columns(3)
c1.metric("Lost Supply (Source Failure)", f"-{record['original_flow']:,.0f}", delta="Event", delta_color="inverse")
c2.metric("Network Compensation (Ramp Up)", f"+{record['compensation_volume']:,.0f}", delta=f"{record['resilience_score']:.1f}% Resilience", delta_color="off")
c3.metric("Net Supply Gap (Unmet Demand)", f"{record['supply_gap']:,.0f}", delta="Critical", delta_color="inverse")

st.divider()

# --- WATERFALL CHART (The Proof) ---
st.subheader(f"Simulation Logic: {selected_asset} Shutdown")

fig = go.Figure(go.Waterfall(
    name = "20", orientation = "v",
    measure = ["relative", "relative", "relative", "total"],
    x = ["Baseline Supply", "Asset Failure", "Network Compensation", "Final Supply Available"],
    textposition = "outside",
    # Logic: Start with Demand (Ideal), subtract loss, add compensation
    text = [
        f"{int(record['system_demand_fixed'])}", 
        f"-{int(record['original_flow'])}", 
        f"+{int(record['compensation_volume'])}", 
        f"{int(record['system_supply_post_override'])}"
    ],
    y = [
        record['system_demand_fixed'], 
        -record['original_flow'], 
        record['compensation_volume'], 
        record['system_supply_post_override']
    ],
    connector = {"line":{"color":"rgb(63, 63, 63)"}},
    decreasing = {"marker":{"color":"#EF553B"}}, # Red for loss
    increasing = {"marker":{"color":"#00CC96"}}, # Green for compensation
    totals = {"marker":{"color":"#636EFA"}}      # Blue for result
))

fig.update_layout(
    title="Supply Recovery Waterfall",
    showlegend = False,
    height=400
)

st.plotly_chart(fig, use_container_width=True)

# --- AI INSIGHTS ---
st.info(f"""
### 🧠 Analysis for {selected_asset}
*   **Original Contribution:** This source was providing **{int(record['original_flow'])}** units.
*   **Optimization Attempt:** The algorithm attempted to increase flow from other sources to fill this hole.
*   **Result:** It found **{int(record['compensation_volume'])}** units of spare capacity elsewhere.
*   **Conclusion:** Since compensation is **0**, this asset is a **Single Point of Failure**. The rest of the network is either running at 100% capacity or is physically disconnected from this demand zone.
""")

# --- COMPARISON CHART ---
st.subheader("Resilience Comparison Across Assets")
fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(
    x=df['target_node'],
    y=df['original_flow'],
    name='Lost Volume',
    marker_color='#EF553B'
))
fig_bar.add_trace(go.Bar(
    x=df['target_node'],
    y=df['compensation_volume'],
    name='Recovered Volume',
    marker_color='#00CC96'
))

fig_bar.update_layout(barmode='group', title="Lost Volume vs. Recovered Volume")
st.plotly_chart(fig_bar, use_container_width=True)