import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# Page Configuration
st.set_page_config(page_title="Lee Woo Sing College - Facilities Energy Action Desk", layout="wide")

st.title("⚡ Lee Woo Sing College: Facilities Energy Action Desk")
st.markdown("A practical management tool to track electricity usage, spot broken air conditioners, and fix room temperature issues across Hostels 4 and 5.")

# Sidebar: File Upload & Controls with Info Tooltips (ℹ️)
st.sidebar.header("1. Upload Monthly Data")
uploaded_file = st.sidebar.file_uploader("Upload LWS Data Excel Log (.xlsx)", type=["xlsx"])

st.sidebar.header("2. Filtering Settings")

# Slider with built-in info tooltip explaining the exact statistical formula
sensitivity = st.sidebar.slider(
    "Detection Sensitivity (How strict)", 
    min_value=1.0, max_value=3.0, value=1.5, step=0.1,
    help="Technical Formula: Z-Score Threshold (Z = (x - μ) / σ). "
         "x is the room's per-student kWh, μ is the monthly peer average across all rooms, "
         "and σ is the standard deviation. A setting of 1.5 flags rooms consuming 1.5 standard deviations above the monthly mean."
)

min_months = st.sidebar.slider(
    "Minimum Months Problematic", 
    min_value=1, max_value=12, value=3,
    help="Persistence Filter: Ensures a room must be flagged as an outlier for at least N separate months "
         "before appearing on the priority maintenance queue, filtering out temporary one-off behavioral spikes."
)

# Confirmed 32 Triple Rooms
TRIPLE_ROOMS = [
    'NG06', 'NG07', 'NG08', 'NG09', 'NG10', 'NG11', 'NG12', 'NG14', 'NG15',
    'N215', 'N415', 'N515', 'N705', 'N706', 'N708', 'N715',
    'S302', 'S502', 'S602', 'S702',
    'S805', 'S806', 'S807', 'S905', 'S906', 'S907',
    'S1005', 'S1006', 'S1007', 'S1105', 'S1106', 'S1107'
]

@st.cache_data
def load_and_process_clean(file):
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
    
    # Metadata & Occupancy Normalization (Adjusting for 2 vs 3 students)
    energy_df['Tenants'] = energy_df['Room'].apply(lambda r: 3 if r in TRIPLE_ROOMS else 2)
    energy_df['Per_Student_kWh'] = energy_df['kWh'] / energy_df['Tenants']
    
    def parse_room_metadata(r):
        block = r[0] 
        rest = r[1:]
        if rest.startswith('G'): 
            floor = 0
            unit_num = int(rest[2:]) if len(rest) > 2 else 0
        elif len(rest) == 4: 
            floor = int(rest[:2])
            unit_num = int(rest[2:])
        else: 
            floor = int(rest[0])
            unit_num = int(rest[1:])
            
        if block == 'S':
            orientation = 'North-Facing (Shaded)' if unit_num <= 12 else 'South-Facing (Sunny)'
        else:
            orientation = 'West-Facing (Afternoon Heat)' if unit_num <= 12 else 'East-Facing (Morning Sun)'
            
        return pd.Series([block, floor, unit_num, orientation])
    
    energy_df[['Block', 'Floor', 'Unit_Num', 'Orientation']] = energy_df['Room'].apply(parse_room_metadata)
    
    # Statistical baseline comparison per month
    energy_df['Monthly_Avg'] = energy_df.groupby('Month')['Per_Student_kWh'].transform('mean')
    energy_df['Monthly_Std'] = energy_df.groupby('Month')['Per_Student_kWh'].transform('std')
    energy_df['Deviation_Score'] = (energy_df['Per_Student_kWh'] - energy_df['Monthly_Avg']) / energy_df['Monthly_Std']
    
    return energy_df

if uploaded_file is not None:
    data = load_and_process_clean(uploaded_file)
    
    # Summary Metrics
    col1, col2, col3, col4 = st.columns(4)
    flagged = data[data['Deviation_Score'] > sensitivity]
    maintenance_list = flagged.groupby(['Room', 'Block', 'Floor', 'Orientation', 'Tenants']).agg(
        Months_Flagged=('Deviation_Score', 'count'),
        Avg_Usage_Per_Student=('Per_Student_kWh', 'mean')
    ).reset_index()
    action_queue = maintenance_list[maintenance_list['Months_Flagged'] >= min_months].sort_values(by='Months_Flagged', ascending=False)
    
    col1.metric("Rooms Monitored", data['Room'].nunique())
    col2.metric("Total Records Tracked", len(data))
    col3.metric("Rooms Needing Inspection", len(action_queue))
    col4.metric("Top Priority Room", action_queue.iloc[0]['Room'] if len(action_queue) > 0 else "None")

    # Clean, Non-Technical Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🚨 What to Fix First (Action List)", 
        "☀️ Room Heat & Sun Exposure Guide", 
        "🚪 Room Directory & Occupancy",
        "🔍 Look Up Individual Room History"
    ])
    
    with tab1:
        st.subheader("Actionable Maintenance Work Order")
        st.write("These rooms consume significantly more electricity per student than the rest of the dorm over multiple months, indicating faulty air conditioning equipment or poor window insulation.")
        
        if len(action_queue) > 0:
            top_spot = action_queue.iloc[0]['Room']
            st.error(f"⚠️ **Immediate Priority:** Dispatch a technician to check **Room {top_spot}**. It has flagged high energy spikes in {action_queue.iloc[0]['Months_Flagged']} separate months.")
        
        st.dataframe(action_queue, use_container_width=True)
        
        csv_export = action_queue.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Work Order for Technicians (CSV)", csv_export, "Maintenance_Action_List.csv", "text/csv")

    with tab2:
        st.subheader("Why Certain Rooms Use More Power (Sun & Heat Study)")
        st.write("Based on the building blueprints, rooms facing the West (North Block units 1–12) and upper floors take direct afternoon sunlight, requiring much more cooling power.")
        
        sun_summary = data.groupby('Orientation')['Per_Student_kWh'].mean().reset_index()
        fig_sun = px.bar(
            sun_summary, x='Orientation', y='Per_Student_kWh',
            title="Average Electricity Used per Student Based on Which Way the Room Windows Face",
            labels={'Per_Student_kWh': 'Average Monthly kWh per Student'}
        )
        st.plotly_chart(fig_sun, use_container_width=True)

    with tab3:
        st.subheader("Hostel Room Directory & Student Capacity")
        st.write("Quick reference showing whether a room holds 2 or 3 students, and its window direction.")
        directory = data[['Room', 'Block', 'Floor', 'Tenants', 'Orientation']].drop_duplicates().sort_values('Room')
        st.dataframe(directory, use_container_width=True)

    with tab4:
        st.subheader("Individual Room History Inspector")
        chosen_room = st.selectbox("Select a room number to inspect:", sorted(data['Room'].unique()), index=sorted(data['Room'].unique()).index('S417') if 'S417' in data['Room'].unique() else 0)
        room_history = data[data['Room'] == chosen_room]
        
        meta = room_history.iloc[0]
        st.info(f"**Room Details:** Block {meta['Block']} | Floor {meta['Floor']} | Capacity: {meta['Tenants']} Students | Window Facing: {meta['Orientation']}")
        
        fig_hist = px.line(
            room_history, x='Month', y='Per_Student_kWh', markers=True,
            title=f"Electricity Use Over Time for Room {chosen_room} (Per Student kWh)"
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    # Collapsible Technical Section for Scholarship Reviewers & Judges
    with st.expander("🔬 Engineering Methodology & Mathematical Formulas (For Reviewers)"):
        st.markdown("""
        If you are evaluating this platform for technical and algorithmic rigor, here are the underlying calculations used:
        1. **Per-Capita Occupancy Normalization:** 
           $$\\text{Per\\_Student\\_kWh} = \\frac{\\text{Total Room kWh}}{\\text{Tenants (2 or 3)}}$$
           *Ensures high consumption isn't falsely blamed on rooms housing 3 students instead of 2.*
        2. **Dynamic Monthly Z-Score Outlier Detection:** 
           $$Z = \\frac{x - \\mu}{\\sigma}$$
           Where $x$ is a room's per-student kWh, $\\mu$ is the monthly mean across all dorms, and $\\sigma$ is the standard deviation. This neutralizes seasonal weather shifts (e.g., higher summer cooling usage across the entire building) while isolating true mechanical hardware malfunctions.
        3. **Facade Orientation Mapping:** Room numbers are programmatically parsed (e.g., North Block units 1–12 mapped to West-facing solar radiation exposure) to quantify micro-climate thermal penalties.
        """)
else:
    st.info("👈 Please upload your `LWS Data.xlsx` file in the sidebar to get started.")
