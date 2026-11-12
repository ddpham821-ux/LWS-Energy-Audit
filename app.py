import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# Page Config
st.set_page_config(page_title="LWS Smart Energy Audit Engine", layout="wide")

st.title("⚡ Lee Woo Sing College: Smart Energy Diagnostics & Equity Engine")
st.markdown("Automated infrastructure fault detection and structural thermal fairness auditing across 300 residential rooms.")

# Sidebar: File Upload & Controls
st.sidebar.header("1. Data Input")
uploaded_file = st.sidebar.file_uploader("Upload WS Power Excel Log (.xlsx)", type=["xlsx"])

st.sidebar.header("2. Diagnostic Parameters")
z_threshold = st.sidebar.slider("Anomaly Z-Score Threshold", min_value=1.0, max_value=2.5, value=1.5, step=0.1)
min_flags = st.sidebar.slider("Minimum Months Flagged (Persistence)", min_value=1, max_value=10, value=3)

# Confirmed 32 Triple Rooms
TRIPLE_ROOMS = [
    'NG06', 'NG07', 'NG08', 'NG09', 'NG10', 'NG11', 'NG12', 'NG14', 'NG15',
    'N215', 'N415', 'N515', 'N705', 'N706', 'N708', 'N715',
    'S302', 'S502', 'S602', 'S702',
    'S805', 'S806', 'S807', 'S905', 'S906', 'S907',
    'S1005', 'S1006', 'S1007', 'S1105', 'S1106', 'S1107'
]

@st.cache_data
def load_and_process(file):
    df = pd.read_excel(file, sheet_name=0)
    long_dfs = []
    for chunk_start in range(0, 30, 10):
        cols = df.columns[chunk_start:chunk_start+10]
        if len(cols) > 1:
            sub_df = df[cols].copy()
            room_col = cols[0]
            date_cols = cols[1:]
            melted = sub_df.melt(id_vars=[room_col], value_vars=date_cols, var_name='Month', value_name='kWh')
            melted = melted.rename(columns={room_col: 'Room'})
            melted = melted[melted['kWh'].notnull() & (melted['kWh'] > 0)]
            long_dfs.append(melted)
    
    energy_df = pd.concat(long_dfs, ignore_index=True)
    
    # Metadata & Occupancy Normalization
    energy_df['Tenants'] = energy_df['Room'].apply(lambda r: 3 if r in TRIPLE_ROOMS else 2)
    energy_df['kWh_Per_Capita'] = energy_df['kWh'] / energy_df['Tenants']
    
    def parse_room(r):
        block = r[0]
        rest = r[1:]
        if rest.startswith('G'): floor = 0
        elif len(rest) == 4: floor = int(rest[:2])
        else: floor = int(rest[0])
        return pd.Series([block, floor])
    
    energy_df[['Block', 'Floor']] = energy_df['Room'].apply(parse_room)
    
    # Per-Capita Z-Score
    energy_df['Month_Mean_PC'] = energy_df.groupby('Month')['kWh_Per_Capita'].transform('mean')
    energy_df['Month_Std_PC'] = energy_df.groupby('Month')['kWh_Per_Capita'].transform('std')
    energy_df['Z_Score_PC'] = (energy_df['kWh_Per_Capita'] - energy_df['Month_Mean_PC']) / energy_df['Month_Std_PC']
    
    return energy_df

if uploaded_file is not None:
    data = load_and_process(uploaded_file)
    
    # Top KPI Row
    col1, col2, col3, col4 = st.columns(4)
    flagged = data[data['Z_Score_PC'] > z_threshold]
    repeat_offenders = flagged.groupby(['Room', 'Block', 'Floor', 'Tenants']).agg(
        Flags=('Z_Score_PC', 'count'),
        Avg_Per_Capita_kWh=('kWh_Per_Capita', 'mean'),
        Max_Z=('Z_Score_PC', 'max')
    ).reset_index()
    priority_queue = repeat_offenders[repeat_offenders['Flags'] >= min_flags].sort_values(by='Flags', ascending=False)
    
    col1.metric("Total Rooms Audited", data['Room'].nunique())
    col2.metric("Months Analyzed", data['Month'].nunique())
    col3.metric("Priority Maintenance Rooms", len(priority_queue))
    col4.metric("Top Persistent Outlier", priority_queue.iloc[0]['Room'] if len(priority_queue) > 0 else "None")

    # Tabs for the Two Core Modules
    tab1, tab2, tab3 = st.tabs(["🔧 Module 1: Hardware Fault Queue", "⚖️ Module 2: Thermal Equity Audit", "🔍 Module 3: Single-Room Inspector"])
    
    with tab1:
        st.subheader("Occupancy-Adjusted Hardware Maintenance Priority List")
        st.write("Rooms listed below consistently exceed peer per-capita consumption across multiple academic years, indicating AC compressor degradation or thermal seal leaks.")
        
        fig_anom = px.bar(
            priority_queue.head(15), x='Room', y='Flags', color='Tenants',
            title="Top Persistent Energy Outliers (Normalized for 2 vs. 3 Tenants)",
            labels={'Flags': 'Months Flagged (Z > Threshold)', 'Tenants': 'Room Capacity'}
        )
        st.plotly_chart(fig_anom, use_container_width=True)
        
        st.dataframe(priority_queue, use_container_width=True)
        csv = priority_queue.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Maintenance Work Order (CSV)", csv, "LWS_Maintenance_Priority_Queue.csv", "text/csv")

    with tab2:
        st.subheader("Structural Thermal Fairness Across Floors & Blocks")
        summer_df = data[data['Month'].str.startswith(('Sep', 'Oct', 'May'))]
        floor_eq = summer_df.groupby(['Block', 'Floor'])['kWh_Per_Capita'].mean().reset_index()
        
        fig_eq = px.bar(
            floor_eq, x='Floor', y='kWh_Per_Capita', color='Block', barmode='group',
            title="Summer Per-Capita Cooling Load by Floor Level (North vs. South Block)",
            labels={'kWh_Per_Capita': 'Avg Monthly kWh per Student'}
        )
        st.plotly_chart(fig_eq, use_container_width=True)

    with tab3:
        st.subheader("Historical Room Trajectory & Intervention Tracker")
        selected_room = st.selectbox("Select Room ID to Inspect:", sorted(data['Room'].unique()), index=sorted(data['Room'].unique()).index('S417') if 'S417' in data['Room'].unique() else 0)
        room_hist = data[data['Room'] == selected_room]
        
        fig_room = go.Figure()
        fig_room.add_trace(go.Scatter(x=room_hist['Month'], y=room_hist['kWh_Per_Capita'], mode='lines+markers', name=f'{selected_room} (Per Capita)'))
        fig_room.add_trace(go.Scatter(x=room_hist['Month'], y=room_hist['Month_Mean_PC'], mode='lines', name='Dorm Peer Average', line=dict(dash='dash', color='gray')))
        fig_room.update_layout(title=f"25-Month Trajectory: {selected_room} vs. Dormitory Baseline", yaxis_title="kWh per Student")
        st.plotly_chart(fig_room, use_container_width=True)
else:
    st.info("👈 Upload `LWS Data.xlsx` in the left sidebar to launch the live diagnostic audit.")