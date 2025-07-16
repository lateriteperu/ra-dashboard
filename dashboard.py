import streamlit as st
import pandas as pd
import plotly.express as px

# --- PAGE SETUP & CONSTANTS ---
st.set_page_config(
    page_title="Farmer Monitoring Dashboard",
    page_icon="🌾",
    layout="wide"
)

# Define the overall project target and the lists of villages by type
OVERALL_TARGET = 120
CERTIFIED_VILLAGES = [
    'ALTO ANDINO', 'ALTO RIOJA', 'DINAMARCA', 'FLOR DE MAYO',
    'FLOR DE PRIMAVERA', 'GERVACIO', 'HUICUNGO', 'MONTE RICO',
    'SANTA MARTHA', 'VILLA HERMOSA'
]
PROJECT_VILLAGES = [
    'ALTO SHAMBOYAKU', 'CHUMBAQUIHUI', 'KACHIPAMPA'
]
ALL_VILLAGES = sorted(CERTIFIED_VILLAGES + PROJECT_VILLAGES)


# --- DATA LOADING (IMPROVED WITH ERROR HANDLING) ---
@st.cache_data
def load_data():
    """
    Loads raw survey data from a single CSV file.
    This version is more robust and checks for common column name variations.
    """
    try:
        # Use the corrected filename
        df_raw = pd.read_csv('Raw_data.csv')

        # --- Find required columns (Date and Village) ---
        # Updated mapping with 'today' and 'village' as primary names
        column_map = {
            'Date': ['today', 'Date', 'date', 'Fecha'],
            'Village': ['village', 'Village', 'Aldea', 'Comunidad']
        }
        
        found_columns = {}
        for target_name, possible_names in column_map.items():
            for name in possible_names:
                if name in df_raw.columns:
                    found_columns[target_name] = name
                    break
        
        # Check if all required columns were found and show a helpful error if not
        if 'Date' not in found_columns or 'Village' not in found_columns:
            error_msg = "Error: Could not find required columns. "
            if 'Date' not in found_columns:
                error_msg += "Please ensure your CSV has a 'Date' or 'today' column. "
            if 'Village' not in found_columns:
                error_msg += "Please ensure you have a 'Village' or 'village' column. "
            error_msg += f"The columns found were: {df_raw.columns.tolist()}"
            st.error(error_msg)
            return None

        # Rename columns to a standard name for the rest of the script
        rename_dict = {v: k for k, v in found_columns.items()}
        df_raw.rename(columns=rename_dict, inplace=True)

        # --- Data Cleaning and Processing ---
        df_raw['Date'] = pd.to_datetime(df_raw['Date'], dayfirst=True, errors='coerce')
        df_raw['Village'] = df_raw['Village'].str.upper()
        
        df_raw.dropna(subset=['Date'], inplace=True)

        return df_raw
    except FileNotFoundError:
        # Updated error message with the correct filename
        st.error("Error: Make sure the file 'Raw_data.csv' is in the same folder as the script.")
        return None

# Load data when the app starts.
df_raw = load_data()

if df_raw is None:
    st.stop()


# --- BRANDED HEADER ---
# Get the last date from the data for the "Last Updated" info
last_update_date = df_raw['Date'].max().strftime("%B %d, %Y")

# Create two columns for the branded header
header_col1, header_col2 = st.columns(2)

with header_col1:
    st.title("Thriving Landscapes San Martin")
    st.markdown("For: **Rainforest Alliance**")

with header_col2:
    # Use markdown with HTML to right-align the text
    st.markdown(
        f"""
        <div style='text-align: right;'>
            Powered by <strong>Laterite</strong><br>
            Last Updated: {last_update_date}
        </div>
        """,
        unsafe_allow_html=True
    )

# Add a separator line
st.markdown("---")


# --- SIDEBAR WITH FILTERS ---
st.sidebar.header("Dashboard Filters")

# NEW: Filter by Village Type
village_type = st.sidebar.radio(
    "Select Village Type:",
    ('All', 'Certified Villages', 'Project Villages')
)

# Filter by individual Village
village_list = ['All'] + ALL_VILLAGES
selected_village = st.sidebar.selectbox("Select Individual Village:", village_list)

# Filter by Date Range
min_date = df_raw['Date'].min()
max_date = df_raw['Date'].max()
selected_dates = st.sidebar.date_input(
    "Select Date Range:",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# --- FILTERING DATA BASED ON SELECTIONS ---
start_date = pd.to_datetime(selected_dates[0])
end_date = pd.to_datetime(selected_dates[1])

# 1. Filter by date first
df_filtered = df_raw[
    (df_raw['Date'] >= start_date) & (df_raw['Date'] <= end_date)
]

# 2. Filter by Village Type
if village_type == 'Certified Villages':
    df_filtered = df_filtered[df_filtered['Village'].isin(CERTIFIED_VILLAGES)]
    active_village_list = CERTIFIED_VILLAGES
elif village_type == 'Project Villages':
    df_filtered = df_filtered[df_filtered['Village'].isin(PROJECT_VILLAGES)]
    active_village_list = PROJECT_VILLAGES
else:
    active_village_list = ALL_VILLAGES


# 3. Filter by individual village
if selected_village != 'All':
    df_filtered = df_filtered[df_filtered['Village'] == selected_village]


# --- KPI CALCULATION ---
total_achieved = len(df_filtered)
# The overall progress percentage is calculated against the total data within the date range, ignoring village filters
overall_progress_df = df_raw[(df_raw['Date'] >= start_date) & (df_raw['Date'] <= end_date)]
if OVERALL_TARGET > 0:
    percentage_achieved = (len(overall_progress_df) / OVERALL_TARGET)
else:
    percentage_achieved = 0

# --- DISPLAY KEY METRICS ---
st.header("Overall Summary")
col1, col2, col3 = st.columns(3)
col1.metric("Overall Target", f"{OVERALL_TARGET:,}")
col2.metric("Total Achieved (in selection)", f"{total_achieved:,}")
col3.metric("Overall Project Progress", f"{percentage_achieved:.1%}")


# --- PROGRESS TABLE BY VILLAGE ---
st.header("Progress by Village")

# Calculate the total achieved for each village from the filtered data
progress_by_village = df_filtered.groupby('Village').size().reset_index(name='Achieved')

# Create a base dataframe with all relevant villages and their types
village_type_map = {village: 'Certified' for village in CERTIFIED_VILLAGES}
village_type_map.update({village: 'Project' for village in PROJECT_VILLAGES})
df_all_villages = pd.DataFrame(list(village_type_map.items()), columns=['Village', 'Type'])

# Filter this base list by the selected type
if village_type == 'Certified Villages':
    df_all_villages = df_all_villages[df_all_villages['Type'] == 'Certified']
elif village_type == 'Project Villages':
    df_all_villages = df_all_villages[df_all_villages['Type'] == 'Project']

# Merge the base list with the achieved counts
village_summary = pd.merge(df_all_villages, progress_by_village, on='Village', how='left')
village_summary['Achieved'] = village_summary['Achieved'].fillna(0).astype(int)

# Display the table
st.dataframe(
    village_summary.style.format({'Achieved': '{:,}'}),
    use_container_width=True
)


# --- CHARTS ---
st.header("Trend Analysis")
col_graph1, col_graph2 = st.columns(2)

with col_graph1:
    st.subheader("Surveys Completed per Day")
    surveys_per_day = df_filtered.groupby(df_filtered['Date'].dt.date).size().reset_index(name='Count')
    # Use the Laterite Dark Red color for the bars
    fig_bars = px.bar(
        surveys_per_day, x='Date', y='Count', title='Daily Survey Volume',
        labels={'Date': 'Day', 'Count': 'No. of Surveys'},
        color_discrete_sequence=['rgb(218, 48, 44)']
    )
    # CHANGE: Format the x-axis to show only the date
    fig_bars.update_xaxes(tickformat="%Y-%m-%d")
    fig_bars.update_layout(title_x=0.5)
    st.plotly_chart(fig_bars, use_container_width=True)

with col_graph2:
    st.subheader("Cumulative Progress Over Time")
    surveys_per_day = surveys_per_day.sort_values('Date')
    surveys_per_day['Cumulative'] = surveys_per_day['Count'].cumsum()
    # Use the Laterite Light Green color for the line
    fig_line = px.line(
        surveys_per_day, x='Date', y='Cumulative', title='Cumulative Survey Growth',
        labels={'Date': 'Day', 'Cumulative': 'Cumulative Total'},
        color_discrete_sequence=['rgb(125, 217, 186)']
    )
    # CHANGE: Format the x-axis to show only the date
    fig_line.update_xaxes(tickformat="%Y-%m-%d")
    fig_line.update_traces(mode='lines+markers')
    fig_line.update_layout(title_x=0.5)
    st.plotly_chart(fig_line, use_container_width=True)


# --- RAW DATA VIEW ---
with st.expander("View filtered raw data"):
    st.dataframe(df_filtered)
