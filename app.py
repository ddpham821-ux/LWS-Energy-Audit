import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# Page Configuration
st.set_page_config(page_title="Lee Woo Sing College - Facilities Energy Action Desk", layout="wide")

st.title("⚡ Lee Woo Sing College: Facilities Energy Action Desk")
st.markdown("A practical management tool to track electricity usage, spot broken air conditioners, and improve room comfort fairly across Hostels 4 and 5.")

# Sidebar: File Upload & Controls with Info Tooltips (ℹ️)
st.sidebar.header("1. Upload Monthly Data")
uploaded_file = st.sidebar.file_uploader("Upload LWS Data Excel Log (.xlsx)", type=["xlsx"])

st.sidebar.header("2. Filtering Settings")

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
    
    # Metadata & Occupancy Normalization
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

    # Clean, Non-Technical Tabs (Added Fair Policy & Next Steps Tab)
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🚨 What to Fix First (Action List)", 
        "💡 Fair Policy & Next Steps",
        "☀️ Room Heat & Sun Exposure Guide", 
        "🏢 Floor & Facade Peer Comparison",
        "🚪 Room Directory & Occupancy",
        "🔍 Intuitive Room Inspector"
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
        st.subheader("💡 Recommended Next Steps & Student-Friendly Policies")
        st.write("How Lee Woo Sing College can reduce energy waste fairly without triggering student complaints over unequal electricity allowances:")
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            st.info("""
            #### 1. Fix Hardware, Not Quotas
            **Why:** Giving certain rooms different free electricity allowances often creates student jealousy and complaints.
            
            **Action:** Keep standard quotas transparent, and instead use the **Action List** to repair faulty AC units in flagged rooms before summer move-in.
            """)
            
        with col_b:
            st.success("""
            #### 2. Passive Sun-Blocking Retrofits
            **Why:** West-facing rooms (North Block units 1–12) and top floors suffer unavoidable afternoon heat gain.
            
            **Action:** Prioritize UV-blocking window films, external shading, or roof insulation on top floors to eliminate the structural cooling penalty at its source.
            """)
            
        with col_c:
            st.warning("""
            #### 3. Positive "Green Dorm" Rewards
            **Why:** Penalties frustrate residents, whereas positive incentives drive voluntary conservation.
            
            **Action:** Introduce a semesterly *Green Dorm Challenge* where rooms staying below their sun-adjusted peer average earn laundry credits or college perks.
            """)
            
        st.divider()
        st.markdown("### 📋 Discussion Checklist for Facilities Management")
        st.markdown("""
        * **Top-Up Data Review:** Cross-reference our flagged rooms with historical student electricity top-up records to see which floors pay the most out-of-pocket.
        * **Pilot Floor Test:** Run a one-semester pilot on Floor 7 (top floor) vs. Floor 2 to measure exact kWh savings after window film or AC servicing.
        * **Weather-Adjusted Baselines:** Consider scaling summer baseline allowances automatically during extreme Hong Kong Observatory heatwaves.
        """)

    with tab3:
        st.subheader("Why Certain Rooms Use More Power (Sun & Heat Study)")
        st.write("Based on the building blueprints, rooms facing the West (North Block units 1–12) and upper floors take direct afternoon sunlight, requiring much more cooling power.")
        
        sun_summary = data.groupby('Orientation')['Per_Student_kWh'].mean().reset_index()
        fig_sun = px.bar(
            sun_summary, x='Orientation', y='Per_Student_kWh',
            title="Average Electricity Used per Student Based on Which Way the Room Windows Face",
            labels={'Per_Student_kWh': 'Average Monthly kWh per Student'}
        )
        st.plotly_chart(fig_sun, use_container_width=True)

    with tab4:
        st.subheader("Compare Rooms on the Same Floor or Sun Exposure")
        st.write("Select a floor or orientation to see how rooms compare side-by-side under identical thermal conditions.")
        
        comp_mode = st.radio("Comparison Mode:", ["By Floor Level", "By Sun/Facade Orientation"], horizontal=True)
        
        if comp_mode == "By Floor Level":
            selected_block_comp = st.selectbox("Select Block:", sorted(data['Block'].unique()), key='comp_block')
            selected_floor_comp = st.selectbox("Select Floor:", sorted(data[data['Block'] == selected_block_comp]['Floor'].unique()), key='comp_floor')
            
            subset = data[(data['Block'] == selected_block_comp) & (data['Floor'] == selected_floor_comp)]
            
            fig_comp = px.bar(
                subset, x='Room', y='Per_Student_kWh', color='Month', barmode='group',
                title=f"Per-Student Energy Comparison Across Block {selected_block_comp}, Floor {selected_floor_comp}"
            )
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            selected_orient = st.selectbox("Select Window Facade Orientation:", sorted(data['Orientation'].unique()))
            subset = data[data['Orientation'] == selected_orient]
            
            fig_orient = px.box(
                subset, x='Room', y='Per_Student_kWh',
                title=f"Energy Distribution for Rooms Facing: {selected_orient}"
            )
            st.plotly_chart(fig_orient, use_container_width=True)

    with tab5:
        st.subheader("Hostel Room Directory & Student Capacity")
        st.write("Quick reference showing whether a room holds 2 or 3 students, and its window direction.")
        directory = data[['Room', 'Block', 'Floor', 'Tenants', 'Orientation']].drop_duplicates().sort_values('Room')
        st.dataframe(directory, use_container_width=True)

    with tab6:
        st.subheader("Intuitive Room Inspector (No Scrolling)")
        st.write("Easily filter down to the room you want by picking its building block and floor first.")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            sel_block = st.selectbox("1. Select Block:", sorted(data['Block'].unique()))
        with c2:
            available_floors = sorted(data[data['Block'] == sel_block]['Floor'].unique())
            sel_floor = st.selectbox("2. Select Floor:", available_floors)
        with c3:
            available_rooms = sorted(data[(data['Block'] == sel_block) & (data['Floor'] == sel_floor)]['Room'].unique())
            sel_room = st.selectbox("3. Select Room Number:", available_rooms)
            
        room_history = data[data['Room'] == sel_room]
        meta = room_history.iloc[0]
        
        st.info(f"**Room Details:** Room **{sel_room}** | Block {meta['Block']} | Floor {meta['Floor']} | Capacity: {meta['Tenants']} Students | Window Facing: {meta['Orientation']}")
        
        fig_hist = px.line(
