import streamlit as st
import pandas as pd
import json
import os
import matplotlib.pyplot as plt
import numpy as np

# Page Config
st.set_page_config(page_title="Gas Network Optimization Dashboard", layout="wide")

# Title
st.title("Gas Network Optimization & Feasibility Dashboard")

# Helper to load data
@st.cache_data
def load_data():
    base_path = os.path.dirname(__file__)
    data_store = {}

    # 1. Load Financial Parameters (CSV)
    fin_path = os.path.join(base_path, 'Financial_Parameters.csv')
    if os.path.exists(fin_path):
        data_store['fin'] = pd.read_csv(fin_path)
    else:
        data_store['fin'] = None

    # 2. Load Simulation Results (JSON)
    sim_path = os.path.join(base_path, 'shutdown_simulation_results.json')
    if os.path.exists(sim_path):
        with open(sim_path, 'r') as f:
            data_store['sim'] = json.load(f)
    else:
        data_store['sim'] = None

    # 3. Load Network Structure (JSON) - NEW
    net_path = os.path.join(base_path, 'network_graph_structure.json')
    if os.path.exists(net_path):
        with open(net_path, 'r') as f:
            data_store['network'] = json.load(f)
    else:
        data_store['network'] = None
        
    # 4. Load Base Case Solution (JSON) - NEW
    base_case_path = os.path.join(base_path, 'base_case_solution.json')
    if os.path.exists(base_case_path):
        with open(base_case_path, 'r') as f:
            data_store['base_case'] = json.load(f)
    else:
        data_store['base_case'] = None

    return data_store

data = load_data()

# Check critical files
if data['sim'] is not None:
    
    # --- SIDEBAR ---
    st.sidebar.header("Scenario Selection")
    json_sim = data['sim']
    scenarios = json_sim.get('scenarios', {})
    scenario_names = list(scenarios.keys())
    
    selected_scenario_name = st.sidebar.selectbox("Select Shutdown Scenario", scenario_names)
    selected_data = scenarios[selected_scenario_name]
    
    # Identify the node being shut down
    target_node_id = selected_data.get('target_node')

    # --- MAIN DASHBOARD ---
    st.subheader(f"KPI Analysis: {selected_scenario_name}")
    
    # Row 1: KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status = selected_data.get('feasibility_status', 'Unknown')
        color = "red" if "Infeasible" in status else "green"
        st.markdown(f"**Feasibility Status**")
        st.markdown(f":{color}[{status}]")
        
    with col2:
        gap = selected_data.get('supply_gap', 0)
        st.metric(label="Supply Gap (1000m³/h)", value=f"{gap:,.2f}", delta=f"-{gap:,.2f}" if gap > 0 else "Stable")
        
    with col3:
        impact = selected_data.get('financial_impact_estimate', 0)
        st.metric(label="Est. Financial Impact (€)", value=f"{impact:,.2f}")
        
    with col4:
        st.metric(label="Target Node", value=target_node_id)

    st.markdown("---")

    # Row 2: Charts and Map
    col_chart, col_map = st.columns([1, 1])
    
    # --- CHART: Supply vs Demand ---
    with col_chart:
        st.subheader("System Balance")
        supply = selected_data.get('system_supply_post_override', 0)
        demand = selected_data.get('system_demand_fixed', 0)
        
        fig_bar, ax_bar = plt.subplots(figsize=(6, 4))
        colors = ['#e74c3c', '#3498db'] if supply < demand else ['#2ecc71', '#3498db']
        bars = ax_bar.bar(['Supply (Post-Shutdown)', 'Demand'], [supply, demand], color=colors)
        ax_bar.set_ylabel("Flow Rate (1000m³/h)")
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax_bar.annotate(f'{height:,.0f}', (bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3), textcoords="offset points", ha='center', va='bottom')
        
        st.pyplot(fig_bar)
        
        # Scenario Details Text
        with st.expander("See Scenario Details JSON"):
            st.json(selected_data)

    # --- MAP: Network Visualization ---
    with col_map:
        st.subheader("Network Topology Map")
        
        if data['network']:
            nodes = data['network'].get('nodes', [])
            
            # Extract coordinates for plotting
            # We categorize them: Sources, Sinks, and the Target Node
            x_sources, y_sources = [], []
            x_sinks, y_sinks = [], []
            x_target, y_target = [], []
            
            target_found = False
            
            for node in nodes:
                n_id = node.get('id')
                # Check if this is the target node (the one shut down)
                is_target = (n_id == target_node_id)
                
                if is_target:
                    x_target.append(node.get('x'))
                    y_target.append(node.get('y'))
                    target_found = True
                elif node.get('Component_Category') == 'source':
                    x_sources.append(node.get('x'))
                    y_sources.append(node.get('y'))
                else:
                    x_sinks.append(node.get('x'))
                    y_sinks.append(node.get('y'))

            # Create Scatter Plot
            fig_map, ax_map = plt.subplots(figsize=(6, 5))
            
            # Plot Sinks (Small grey dots)
            ax_map.scatter(x_sinks, y_sinks, c='#95a5a6', s=10, alpha=0.5, label='Sinks/Nodes')
            
            # Plot Sources (Green triangles)
            ax_map.scatter(x_sources, y_sources, c='#2ecc71', s=80, marker='^', edgecolors='black', label='Active Sources')
            
            # Plot Target Node (Big Red X)
            if target_found:
                ax_map.scatter(x_target, y_target, c='#e74c3c', s=200, marker='X', edgecolors='black', zorder=10, label=f'SHUTDOWN: {target_node_id}')
            
            ax_map.set_title("Gas Network Overview")
            ax_map.set_xlabel("Coordinate X")
            ax_map.set_ylabel("Coordinate Y")
            ax_map.legend(loc='upper right')
            ax_map.grid(True, linestyle='--', alpha=0.3)
            
            st.pyplot(fig_map)
        else:
            st.info("network_graph_structure.json not found. Add file to visualize map.")

    # Row 3: Global Base Case Information (Optional)
    if data['base_case']:
        st.markdown("---")
        st.subheader("Baseline System Health")
        bc = data['base_case']
        
        col_bc1, col_bc2 = st.columns(2)
        with col_bc1:
            st.info(f"**Base Optimization Status:** {bc.get('status', 'Unknown')}")
        with col_bc2:
            st.info(f"**Base Objective Value:** {bc.get('objective_value', 0):,.2f}")

else:
    st.error("Simulation results file (shutdown_simulation_results.json) not found.")