# ui.py

import streamlit as st

def render_analysis_controls(param_options):
    """
    Renders the analysis controls that appear AFTER files are uploaded.
    This function assumes it is called inside an `st.sidebar` context.

    Args:
        param_options (list): A list of parameter names parsed from the uploaded files.

    Returns:
        dict: A dictionary containing all the user's settings.
    """
    # 1. Parameter Selection
    selected_parameter = st.selectbox(
        "Select Parameter to Analyze",
        options=param_options,
        key="selected_parameter" # Add a key for stability
    )

    # 2. Time Window Selection
    time_window_option = st.selectbox(
        "Select Analysis Time Window",
        options=["Entire Dataset", "Last 24 Hours", "Last 48 Hours", "Last 72 Hours", "Custom..."],
        key="time_window_option"
    )
    # Conditional inputs for "Custom..."
    custom_start = None
    custom_end = None
    if time_window_option == "Custom...":
        col1, col2 = st.columns(2)
        with col1:
            custom_start = st.number_input("Start (hours from start)", min_value=0, step=1, key="custom_start")
        with col2:
            custom_end = st.number_input("End (hours from start)", min_value=custom_start or 0, step=1, key="custom_end")

    st.markdown("---")

    # 3. Light/Dark Cycle Configuration
    st.subheader("Light/Dark Cycle")
    light_start = st.slider("Light Cycle Start Hour (24h)", 0, 23, 7, key="light_start")
    light_end = st.slider("Light Cycle End Hour (24h)", 0, 23, 19, key="light_end")

    # --- Return all settings ---
    return {
        "selected_parameter": selected_parameter,
        "time_window_option": time_window_option,
        "custom_start": custom_start,
        "custom_end": custom_end,
        "light_start": light_start,
        "light_end": light_end,
    }


def render_main_view():
    """
    Renders the main content area of the application.
    "Workspace" where results are displayed.
    """
    st.header("CLAMSer: The Bridge from Raw Data to Analysis")
    st.write("Welcome! Start by uploading your CLAMS data files using the sidebar.")
    st.info("Once files are uploaded, configure your analysis using the controls on the left.")