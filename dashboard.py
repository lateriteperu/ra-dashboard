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
last_update_date = df_raw['Date'].max().strftime("%B %d, %Y")

header_col1, header_col2 = st.columns(2)

with header_col1:
    st.title("Thriving Landscapes San Martin")
    # Use markdown with inline CSS to control font size
    st.markdown('<p style="font-size: 20px;">For: <strong>Rainforest Alliance</strong></p>', unsafe_allow_html=True)

with header_col2:
    # Use a container to group the logo and text
    with st.container():
        # Use markdown with inline CSS to control font size
        st.markdown(
            f"""
            <div style='text-align: right; font-size: 20px;'>
                Created by <strong>Laterite</strong><br>
                Last Updated: {last_update_date}
            </div>
            """,
            unsafe_allow_html=True
        )

st.markdown("---")


# --- SIDEBAR WITH FILTERS ---
st.sidebar.header("Dashboard Filters")

village_type = st.sidebar.radio(
    "Select Village Type:",
    ('All', 'Certified Villages', 'Project Villages')
)

village_list = ['All'] + ALL_VILLAGES
selected_village = st.sidebar.selectbox("Select Individual Village:", village_list)

min_date = df_raw['Date'].min()
max_date = df_raw['Date'].max()
selected_dates = st.sidebar.date_input(
    "Select Date Range:",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# --- FILTERING DATA ---
start_date = pd.to_datetime(selected_dates[0])
end_date = pd.to_datetime(selected_dates[1])

# Create a dataframe for overall progress (only filtered by date)
overall_progress_df = df_raw[
    (df_raw['Date'] >= start_date) & (df_raw['Date'] <= end_date)
]

# Create a second dataframe for detailed filtering
df_filtered = overall_progress_df.copy()

if village_type == 'Certified Villages':
    df_filtered = df_filtered[df_filtered['Village'].isin(CERTIFIED_VILLAGES)]
elif village_type == 'Project Villages':
    df_filtered = df_filtered[df_filtered['Village'].isin(PROJECT_VILLAGES)]

if selected_village != 'All':
    df_filtered = df_filtered[df_filtered['Village'] == selected_village]


# --- KPI CALCULATION ---
total_achieved_in_date_range = len(overall_progress_df)
total_achieved_in_selection = len(df_filtered)

if OVERALL_TARGET > 0:
    percentage_achieved = (total_achieved_in_date_range / OVERALL_TARGET)
else:
    percentage_achieved = 0

# --- DISPLAY METRICS ---
st.header("Overall Summary")
col1, col2, col3 = st.columns(3)
col1.metric("Overall Target", f"{OVERALL_TARGET:,}")
col2.metric("Total Achieved (in date range)", f"{total_achieved_in_date_range:,}")
col3.metric("Overall Project Progress", f"{percentage_achieved:.1%}")

st.subheader("Details for Current Selection")
st.metric("Surveys in Selection", f"{total_achieved_in_selection:,}")


# --- PROGRESS TABLE BY VILLAGE ---
st.header("Progress by Village")
progress_by_village = df_filtered.groupby('Village').size().reset_index(name='Achieved')
village_type_map = {village: 'Certified' for village in CERTIFIED_VILLAGES}
village_type_map.update({village: 'Project' for village in PROJECT_VILLAGES})
df_all_villages = pd.DataFrame(list(village_type_map.items()), columns=['Village', 'Type'])

if village_type == 'Certified Villages':
    df_all_villages = df_all_villages[df_all_villages['Type'] == 'Certified']
elif village_type == 'Project Villages':
    df_all_villages = df_all_villages[df_all_villages['Type'] == 'Project']

village_summary = pd.merge(df_all_villages, progress_by_village, on='Village', how='left')
village_summary['Achieved'] = village_summary['Achieved'].fillna(0).astype(int)
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
    fig_bars = px.bar(
        surveys_per_day, x='Date', y='Count', title='Daily Survey Volume',
        labels={'Date': 'Day', 'Count': 'No. of Surveys'},
        color_discrete_sequence=['rgb(218, 48, 44)']
    )
    fig_bars.update_xaxes(tickformat="%Y-%m-%d")
    fig_bars.update_layout(title_x=0.5)
    st.plotly_chart(fig_bars, use_container_width=True)

with col_graph2:
    st.subheader("Cumulative Progress Over Time")
    surveys_per_day = surveys_per_day.sort_values('Date')
    surveys_per_day['Cumulative'] = surveys_per_day['Count'].cumsum()
    fig_line = px.line(
        surveys_per_day, x='Date', y='Cumulative', title='Cumulative Survey Growth',
        labels={'Date': 'Day', 'Cumulative': 'Cumulative Total'},
        color_discrete_sequence=['rgb(125, 217, 186)']
    )
    fig_line.update_xaxes(tickformat="%Y-%m-%d")
    fig_line.update_traces(mode='lines+markers')
    fig_line.update_layout(title_x=0.5)
    st.plotly_chart(fig_line, use_container_width=True)


# --- RAW DATA VIEW ---
with st.expander("View filtered raw data"):
    st.dataframe(df_filtered)
