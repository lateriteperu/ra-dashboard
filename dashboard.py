import streamlit as st
import pandas as pd
import plotly.express as px
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# --- PAGE SETUP & CONSTANTS ---
st.set_page_config(
    page_title="Farmer Monitoring Dashboard",
    page_icon="🌾",
    layout="wide"
)

# Password protection
def check_password():
    """Returns `True` if the user has the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password.
        else:
            st.session_state["password_correct"] = False

    # Return `True` if the user has already entered the correct password.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("Password incorrect")
    return False

if not check_password():
    st.stop()  # Do not continue if the password is wrong.


# Define the overall project target and the lists of villages by type
OVERALL_TARGET = 120
CERTIFIED_VILLAGES = [
    'ALTO ANDINO', 'ALTO RIOJA', 'DINAMARCA', 'FLOR DE MAYO',
    'FLOR DE PRIMAVERA', 'GERVACIO', 'HUICUNGO', 'MONTE RICO',
    'SANTA MARTHA', 'VILLA HERMOSA' , 'EL PARAISO' , 'LA PERLA'
]
PROJECT_VILLAGES = [
    'VISTA ALEGRE', 'CHUMBAQUIHUI', 'KACHIPAMPA'
]
ALL_VILLAGES = sorted(CERTIFIED_VILLAGES + PROJECT_VILLAGES)


# --- DATA LOADING FUNCTIONS ---
def load_survey_data():
    """Loads the main farmer survey data."""
    try:
        df = pd.read_csv('Raw_data.csv')
        column_map = {
            'Date': ['today', 'Date', 'date', 'Fecha'],
            'Village': ['village', 'Village', 'Aldea', 'Comunidad']
        }
        found_columns = {}
        for target_name, possible_names in column_map.items():
            for name in possible_names:
                if name in df.columns:
                    found_columns[target_name] = name
                    break
        if 'Date' not in found_columns or 'Village' not in found_columns:
            raise FileNotFoundError(f"Survey data error: Required columns not found. Found: {df.columns.tolist()}")
        
        rename_dict = {v: k for k, v in found_columns.items()}
        df.rename(columns=rename_dict, inplace=True)
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        df['Village'] = df['Village'].str.upper()
        df.dropna(subset=['Date'], inplace=True)
        return df
    except FileNotFoundError as e:
        # Raise the exception to be caught by the session state loader
        raise e

def load_gps_data():
    """Loads the land use GPS data."""
    try:
        df_gps = pd.read_csv('gps_raw.csv')
        if 'type' not in df_gps.columns:
            raise FileNotFoundError("Error: The 'gps_raw.csv' file must contain a column named 'type'.")
        df_gps['Land Use Type'] = df_gps['type'].str.replace('_', ' ').str.title()
        return df_gps
    except FileNotFoundError:
        return None

def load_map_data():
    """Loads the farm polygon shapefile data from a zip archive."""
    # This function will now raise an exception on failure, which will be caught below.
    gdf = gpd.read_file("zip://Polygons_Shapefile.zip")
    if 'What_is_th' not in gdf.columns:
        raise KeyError("Shapefile error: Must contain a column named 'What_is_th'.")
    return gdf


# --- LOAD ALL DATA INTO SESSION STATE WITH ROBUST ERROR HANDLING ---
if 'survey_data' not in st.session_state:
    try:
        st.session_state.survey_data = load_survey_data()
        st.session_state.survey_error = None
    except Exception as e:
        st.session_state.survey_data = None
        st.session_state.survey_error = e

if 'gps_data' not in st.session_state:
    st.session_state.gps_data = load_gps_data()

if 'map_data' not in st.session_state:
    try:
        st.session_state.map_data = load_map_data()
        st.session_state.map_error = None
    except Exception as e:
        st.session_state.map_data = None
        st.session_state.map_error = e

df_raw = st.session_state.survey_data
df_gps = st.session_state.gps_data
gdf_farms = st.session_state.map_data

# --- ROBUSTNESS CHECK: Ensure survey data is valid before proceeding ---
if st.session_state.survey_error:
    st.error(f"CRITICAL ERROR LOADING SURVEY DATA: {st.session_state.survey_error}")
    st.stop()
if df_raw is None or df_raw.empty:
    st.error("CRITICAL ERROR: 'Raw_data.csv' file is empty or has no valid dates. Please check the file.")
    st.stop()


# --- BRANDED HEADER ---
last_update_date = df_raw['Date'].max().strftime("%B %d, %Y")
header_col1, header_col2 = st.columns(2)
with header_col1:
    st.title("Thriving Landscapes San Martin")
    st.markdown('<p style="font-size: 20px;">For: <strong>Rainforest Alliance</strong></p>', unsafe_allow_html=True)
with header_col2:
    with st.container():
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


# --- TAB STRUCTURE ---
tab1, tab2, tab3 = st.tabs(["Farmer Surveys", "Land Use Analysis", "Farm Polygons Map"])

# --- TAB 1: FARMER SURVEYS ---
with tab1:
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

    if not selected_dates or len(selected_dates) != 2:
        start_date, end_date = min_date, max_date
        st.sidebar.warning("Invalid date range selected. Showing data for all dates.")
    else:
        start_date, end_date = pd.to_datetime(selected_dates[0]), pd.to_datetime(selected_dates[1])

    overall_progress_df = df_raw[(df_raw['Date'] >= start_date) & (df_raw['Date'] <= end_date)]
    df_filtered = overall_progress_df.copy()

    if village_type == 'Certified Villages':
        df_filtered = df_filtered[df_filtered['Village'].isin(CERTIFIED_VILLAGES)]
    elif village_type == 'Project Villages':
        df_filtered = df_filtered[df_filtered['Village'].isin(PROJECT_VILLAGES)]
    if selected_village != 'All':
        df_filtered = df_filtered[df_filtered['Village'] == selected_village]

    total_achieved_in_date_range = len(overall_progress_df)
    total_achieved_in_selection = len(df_filtered)
    percentage_achieved = (total_achieved_in_date_range / OVERALL_TARGET) if OVERALL_TARGET > 0 else 0

    st.header("Overall Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Overall Target", f"{OVERALL_TARGET:,}")
    col2.metric("Total Achieved (in date range)", f"{total_achieved_in_date_range:,}")
    col3.metric("Overall Project Progress", f"{percentage_achieved:.1%}")

    st.subheader("Details for Current Selection")
    st.metric("Surveys in Selection", f"{total_achieved_in_selection:,}")

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
    st.dataframe(village_summary.style.format({'Achieved': '{:,}'}), use_container_width=True)

    st.header("Trend Analysis")
    col_graph1, col_graph2 = st.columns(2)
    with col_graph1:
        st.subheader("Surveys Completed per Day")
        surveys_per_day = df_filtered.groupby(df_filtered['Date'].dt.date).size().reset_index(name='Count')
        fig_bars = px.bar(surveys_per_day, x='Date', y='Count', title='Daily Survey Volume',
                          labels={'Date': 'Day', 'Count': 'No. of Surveys'},
                          color_discrete_sequence=['rgb(218, 48, 44)'])
        fig_bars.update_xaxes(tickformat="%Y-%m-%d")
        fig_bars.update_layout(title_x=0.5)
        st.plotly_chart(fig_bars, use_container_width=True)
    with col_graph2:
        st.subheader("Cumulative Progress Over Time")
        surveys_per_day = surveys_per_day.sort_values('Date')
        surveys_per_day['Cumulative'] = surveys_per_day['Count'].cumsum()
        fig_line = px.line(surveys_per_day, x='Date', y='Cumulative', title='Cumulative Survey Growth',
                           labels={'Date': 'Day', 'Cumulative': 'Cumulative Total'},
                           color_discrete_sequence=['rgb(125, 217, 186)'])
        fig_line.update_xaxes(tickformat="%Y-%m-%d")
        fig_line.update_traces(mode='lines+markers')
        fig_line.update_layout(title_x=0.5)
        st.plotly_chart(fig_line, use_container_width=True)

    with st.expander("View filtered raw data"):
        st.dataframe(df_filtered)

# --- TAB 2: LAND USE ANALYSIS ---
with tab2:
    st.header("Land Use Point Frequency")
    if df_gps is not None:
        frequency = df_gps['Land Use Type'].value_counts().reset_index()
        frequency.columns = ['Land Use Type', 'Number of Points']
        fig_land_use = px.bar(
            frequency, x='Land Use Type', y='Number of Points',
            title='Frequency of Land Use Types',
            labels={'Land Use Type': 'Type of Land Use', 'Number of Points': 'Count of GPS Points'},
            color_discrete_sequence=['rgb(218, 48, 44)']
        )
        fig_land_use.update_layout(title_x=0.5)
        st.plotly_chart(fig_land_use, use_container_width=True)
    else:
        st.warning("Warning: 'gps_raw.csv' file not found. Please add it to your project folder to see this analysis.")

# --- TAB 3: FARM POLYGONS MAP ---
with tab3:
    st.header("Map of Farm Polygons")
    if 'map_error' in st.session_state and st.session_state.map_error is not None:
        st.error(f"A technical error occurred while loading the shapefile: {st.session_state.map_error}")
    elif gdf_farms is not None and not gdf_farms.empty:
        try:
            # --- NEW: Add a search box for farms ---
            farm_id_list = ['All Farms'] + sorted(gdf_farms['What_is_th'].unique().tolist())
            selected_farm_id = st.selectbox("Search for a Farm ID to zoom in:", farm_id_list)

            # Filter the data based on the selection
            if selected_farm_id == 'All Farms':
                gdf_to_display = gdf_farms
            else:
                gdf_to_display = gdf_farms[gdf_farms['What_is_th'] == selected_farm_id]

            # Ensure the GeoDataFrame is in the correct CRS for Folium (WGS 84)
            gdf_4326 = gdf_to_display.to_crs(epsg=4326)

            # Calculate the center for the map view
            bounds = gdf_4326.total_bounds
            center_lat = (bounds[1] + bounds[3]) / 2
            center_lon = (bounds[0] + bounds[2]) / 2

            # Determine the appropriate zoom level
            zoom_level = 12 if selected_farm_id == 'All Farms' else 16

            # Create a base map centered on the data
            m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level, tiles=None, control_scale=True)
            
            folium.TileLayer(
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri', name='Esri Satellite', overlay=False, control=True
            ).add_to(m)
            
            # --- NEW: Define improved styling and highlight functions ---
            style_function = lambda x: {
                'fillColor': '#DA302C', # Laterite Dark Red
                'color': '#FFFFFF',     # White
                'weight': 3,
                'fillOpacity': 1.0      # Not transparent
            }
            highlight_function = lambda x: {
                'fillColor': '#DA302C', # Laterite Dark Red
                'color': '#FFFFFF',
                'weight': 5,            # Thicker border on hover
                'fillOpacity': 1.0      # Still not transparent
            }

            folium.GeoJson(
                gdf_4326,
                tooltip=folium.features.GeoJsonTooltip(
                    fields=['What_is_th'],
                    aliases=['Farm ID:'],
                    sticky=True
                ),
                style_function=style_function,
                highlight_function=highlight_function
            ).add_to(m)
            
            st_folium(m, use_container_width=True, height=600)

        except Exception as e:
            st.error(f"An error occurred during map creation: {e}")

    else:
        st.warning("Could not load map data. Please check the 'Polygons_Shapefile.zip' file.")
