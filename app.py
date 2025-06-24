# app.py

import streamlit as st
import pandas as pd
import ui_components as ui
import processing
import plotting
import io

def main():
    # ... (Page config and file upload blocks are unchanged) ...
    st.set_page_config(
        page_title="CLAMSer v1.0",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    with st.sidebar:
        st.title("🧬 CLAMSer v1.0")
        st.header("File Upload")
        uploaded_files = st.file_uploader(
            "Upload CLAMS Data Files",
            accept_multiple_files=True,
            type=['csv', 'txt'],
            key="main_file_uploader",
            on_change=lambda: st.session_state.update(data_loaded=False)
        )
        st.markdown("---")
    if not uploaded_files:
        ui.render_main_view()
        return
    if not st.session_state.get('data_loaded', False):
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
        st.session_state.data_loaded = True
        if st.session_state.param_options:
            st.info(f"Parsed {len(st.session_state.param_options)} parameter(s) for {len(st.session_state.animal_ids)} animals.")
        else:
            st.error("Parsing failed. No valid parameters found. Please check file formats.")
    if not st.session_state.get('data_loaded', False) or not st.session_state.get('param_options'):
        st.warning("Please upload valid CLAMS data files.")
        return
    with st.sidebar:
        st.header("Analysis Controls")
        analysis_settings = ui.render_analysis_controls(st.session_state.param_options)

    # --- REFACTORED MAIN WORKSPACE ---
    st.header("Analysis Workspace")

    with st.expander("Step 1: Setup Groups & Lean Mass", expanded=True):
        # Call the UI component and store its current state in a variable.
        current_ui_groups = ui.render_group_assignment_ui(st.session_state.animal_ids)
        st.markdown("---")
        ui.render_lean_mass_ui()

    st.markdown("---")
    st.header("Step 2: Configure & Generate Results")

    normalization_mode = st.radio(
        "Select Normalization Mode",
        options=["Absolute Values", "Body Weight Normalized", "Lean Mass Normalized"],
        key="normalization_mode",
        horizontal=True
    )
    if normalization_mode == "Lean Mass Normalized":
        has_file = st.session_state.get('lean_mass_uploader') is not None
        has_text = st.session_state.get('lean_mass_manual_text', '').strip() != ''
        if not has_file and not has_text:
            st.warning("Please provide lean mass data in the 'Setup' section above to use this mode.", icon="⚠️")

    if st.button("Process & Analyze Data", type="primary"):
        # --- KEY CHANGE: Capture UI state ON CLICK ---
        st.session_state.analysis_triggered = True
        st.session_state.group_assignments = current_ui_groups

        # Parse lean mass data (this logic remains the same)
        lean_mass_input = None
        if st.session_state.lean_mass_input_method == "File Upload":
            lean_mass_input = st.session_state.get('lean_mass_uploader')
        else:
            lean_mass_input = st.session_state.get('lean_mass_manual_text', '').strip()
        if lean_mass_input:
            parsed_map, error_msg = processing.parse_lean_mass_data(lean_mass_input)
            if error_msg:
                st.error(f"Lean Mass Data Error: {error_msg}")
                st.session_state.lean_mass_map = {}
            else:
                st.session_state.lean_mass_map = parsed_map
        else:
            st.session_state.lean_mass_map = {}
    
    # --- Results Display (Unchanged) ---
    if st.session_state.get('analysis_triggered', False):
        st.header("Analysis Results")
        selected_param = analysis_settings.get("selected_parameter")
        with st.expander("`[Sanity Check]` Click to view the settings for this analysis"):
            st.write("**Analysis Controls:**", analysis_settings)
            st.write("**Group Assignments (Captured on Process):**", st.session_state.get('group_assignments', {}))
            st.write("**Parsed Lean Mass Data:**", st.session_state.get('lean_mass_map', {}))
        
        if selected_param and selected_param in st.session_state.parsed_data:
            base_df = st.session_state.parsed_data[selected_param].copy()
            df_filtered = processing.filter_data_by_time(base_df, analysis_settings["time_window_option"], analysis_settings["custom_start"], analysis_settings["custom_end"])
            df_processed = processing.add_light_dark_cycle_info(df_filtered, analysis_settings["light_start"], analysis_settings["light_end"])
            
            # This now uses the correctly captured group assignments
            df_with_groups = processing.add_group_info(df_processed, st.session_state.get('group_assignments', {}))
            
            df_normalized = processing.apply_normalization(df_with_groups, normalization_mode, st.session_state.get('lean_mass_map', {}))
            
            if not df_normalized.empty:
                with st.expander("`[Sanity Check]` Data Preview Post-Normalization"):
                    st.write(f"Data after applying **{normalization_mode}**.")
                    st.dataframe(df_normalized.head())
                st.subheader(f"1. Summary Bar Chart for: {selected_param}")
                group_summary_df = processing.calculate_summary_stats_per_group(df_normalized)
                bar_chart_fig = plotting.create_summary_bar_chart(group_summary_df, selected_param)
                st.plotly_chart(bar_chart_fig, use_container_width=True)
                st.subheader(f"2. Interactive Timeline for: {selected_param}")
                timeline_fig = plotting.create_timeline_chart(df_normalized, analysis_settings['light_start'], analysis_settings['light_end'], selected_param)
                st.plotly_chart(timeline_fig, use_container_width=True)
                st.subheader("3. Summary Data Table (per Animal)")
                summary_df_animal = processing.calculate_summary_stats_per_animal(df_normalized)
                st.dataframe(summary_df_animal, use_container_width=True)
            else:
                st.warning("No data remains after applying the selected filters and normalization. Please check your settings, especially the Lean Mass data.")
        else:
            st.warning("A valid parameter must be selected to display results.")

if __name__ == "__main__":
    main()