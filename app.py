# app.py

import streamlit as st
import pandas as pd
import ui_components as ui
import processing
import plotting
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

    # --- Sidebar ---
    with st.sidebar:
        st.title("🧬 CLAMSer v1.0")
        st.header("File Upload")
        uploaded_files = st.file_uploader(
            "Upload CLAMS Data Files",
            accept_multiple_files=True,
            type=['csv', 'txt'],
            key="main_file_uploader",
            # On change, we must clear old processed data to force a re-run
            on_change=lambda: st.session_state.update(data_loaded=False)
        )
        st.markdown("---")


    # --- Main Application Logic ---
    if not uploaded_files:
        ui.render_main_view()
        return

    # === DATA LOADING AND PREPARATION ===
    # This block now only runs if 'data_loaded' is False, which is triggered by new file uploads.
    if not st.session_state.get('data_loaded', False):
        # Initialize all session state variables for a new run
        st.session_state.parsed_data = {}
        st.session_state.param_options = []
        st.session_state.animal_ids = []
        st.session_state.group_assignments = {}
        st.session_state.num_groups = 1
        st.session_state.analysis_triggered = False
        
        all_animal_ids = set()
        
        with st.spinner("Parsing data files..."):
            for file in uploaded_files:
                try:
                    file_content = file.getvalue().decode('utf-8', errors='ignore')
                    lines = file_content.splitlines()
                except Exception as e:
                    st.error(f"Could not read file {file.name}. Error: {e}")
                    continue

                parameter, animal_ids_map, data_start_line = processing.parse_clams_header(lines)
                
                if parameter and data_start_line > -1:
                    if parameter not in st.session_state.param_options:
                        st.session_state.param_options.append(parameter)

                    df_tidy = processing.parse_clams_data(lines, data_start_line, animal_ids_map)
                    
                    if df_tidy is not None and not df_tidy.empty:
                        st.session_state.parsed_data[parameter] = df_tidy
                        all_animal_ids.update(df_tidy['animal_id'].unique())
                    else:
                        st.warning(f"Could not parse data for parameter '{parameter}' in file '{file.name}'.")

        st.session_state.animal_ids = sorted(list(all_animal_ids))
        st.session_state.data_loaded = True # Flag that loading is complete
        
        if st.session_state.param_options:
            st.info(f"Parsed {len(st.session_state.param_options)} parameter(s) for {len(st.session_state.animal_ids)} animals.")
        else:
            st.error("Parsing failed. No valid parameters found. Please check file formats.")


    if not st.session_state.get('data_loaded', False) or not st.session_state.get('param_options'):
        st.warning("Please upload valid CLAMS data files.")
        return

    # === SIDEBAR CONTROLS ===
    with st.sidebar:
        st.header("Analysis Controls")
        analysis_settings = ui.render_analysis_controls(st.session_state.param_options)

    # === MAIN VIEW WORKSPACE ===
    st.header("Analysis Workspace")

    ui.render_setup_expander(st.session_state.animal_ids)
    st.markdown("---")

    st.header("Step 2: Generate Results")
    if st.button("Process & Analyze Data", type="primary"):
        st.session_state.analysis_triggered = True

    # --- RESULTS DISPLAY ---
    if st.session_state.get('analysis_triggered', False):
        st.header("Analysis Results")
        selected_param = analysis_settings.get("selected_parameter")

        st.subheader("1. Active Settings")
        with st.expander("Click to view the settings for this analysis"):
            st.write("**Analysis Controls:**")
            st.json(analysis_settings)
            st.write("**Group Assignments:**")
            # This will now correctly show the saved assignments
            st.json(st.session_state.get('group_assignments', {}))

        if selected_param and selected_param in st.session_state.parsed_data:
            base_df = st.session_state.parsed_data[selected_param]

            df_filtered = processing.filter_data_by_time(
                base_df,
                analysis_settings["time_window_option"],
                analysis_settings["custom_start"],
                analysis_settings["custom_end"]
            )
            df_processed = processing.add_light_dark_cycle_info(
                df_filtered,
                analysis_settings["light_start"],
                analysis_settings["light_end"]
            )
            
            # ** APPLY GROUP INFO TO THE DATAFRAME **
            df_with_groups = processing.add_group_info(
                df_processed, 
                st.session_state.get('group_assignments', {})
            )
            
            st.subheader(f"2. Interactive Timeline for: {selected_param}")
            if not df_with_groups.empty:
                timeline_fig = plotting.create_timeline_chart(
                    df_with_groups, # Pass the dataframe that has group info
                    analysis_settings['light_start'],
                    analysis_settings['light_end'],
                    selected_param
                )
                st.plotly_chart(timeline_fig, use_container_width=True)

                with st.expander("Show Raw Data Preview"):
                    st.write(f"Showing data for the **'{analysis_settings['time_window_option']}'** time window.")
                    st.write(f"Data points remaining after filtering: **{len(df_with_groups)}** (out of {len(base_df)} total)")
                    st.dataframe(df_with_groups.head(10)) # Use the dataframe with group info
            else:
                st.warning("No data remains after applying the selected time filter.")
        else:
            st.warning("A valid parameter must be selected to display results.")

if __name__ == "__main__":
    main()