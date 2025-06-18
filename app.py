# app.py

import streamlit as st
import pandas as pd
import ui
import processing
import io

def main():
    """
    Main function to run the Streamlit application.
    """
    st.set_page_config(
        page_title="CLAMSer v1.0",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Master dictionary to hold all data and settings
    clams_data = {}

    # --- Sidebar ---
    with st.sidebar:
        st.title("🧬 CLAMSer v1.0")
        st.header("File Upload")

        # The one and only file uploader widget
        uploaded_files = st.file_uploader(
            "Upload CLAMS Data Files",
            accept_multiple_files=True,
            type=['csv', 'txt'],
            key="main_file_uploader" # A unique key to prevent errors
        )
        st.markdown("---")

    # --- Main Application Logic ---
    if uploaded_files:
        # If files are uploaded, process them and show analysis controls
        param_options = []
        
        # Store all parsed dataframes in dictionary, keyed by parameter
        parsed_dataframes = {}

        for file in uploaded_files:
            parameter, animal_ids, data_start_line = processing.parse_clams_header(io.BytesIO(file.getvalue()))
            if parameter and parameter not in param_options:
                param_options.append(parameter)
                df_tidy = processing.parse_clams_data(io.BytesIO(file.getvalue()), data_start_line, animal_ids)
                if df_tidy is not None:
                    parsed_dataframes[parameter] = df_tidy

        with st.sidebar:
            st.header("Analysis Controls")
            analysis_settings = ui.render_analysis_controls(param_options)

        # --- Display Results in Main View ---
        st.header("Analysis Results")
        selected_param = analysis_settings.get("selected_parameter")

        # Display settings being used
        st.subheader("1. Active Settings")
        with st.expander("Click to view the settings dictionary", expanded=False):
            st.json(analysis_settings)

        if selected_param and selected_param in parsed_dataframes:
            # Retrieve correct base dataframe
            base_df = parsed_dataframes[selected_param]

            # --- Apply Filtering and Annotation ---
            st.subheader(f"2. Filtered Data for: {selected_param}")
            
            # Step 1: Filter by time window
            df_filtered = processing.filter_data_by_time(
                base_df,
                analysis_settings["time_window_option"],
                analysis_settings["custom_start"],
                analysis_settings["custom_end"]
            )

            # Step 2: Annotate with light/dark cycle
            df_processed = processing.add_light_dark_cycle_info(
                df_filtered,
                analysis_settings["light_start"],
                analysis_settings["light_end"]
            )
            
            if not df_processed.empty:
                st.write(f"Showing data for the **'{analysis_settings['time_window_option']}'** time window.")
                st.write(f"Data points remaining after filtering: **{len(df_processed)}** (out of {len(base_df)} total)")
                
                st.dataframe(df_processed.head())
            else:
                st.warning("No data remains after applying the selected time filter. Please select a different time window.")

        else:
            st.warning("Please select a valid parameter to begin analysis.")

    else:
        # If no files are uploaded, show welcome
        ui.render_main_view()


if __name__ == "__main__":
    main()