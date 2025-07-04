# app.py

import streamlit as st
import pandas as pd
import ui_components as ui
import processing
import plotting
import validation_utils

def main():
    # --- Page & Sidebar Config ---
    st.set_page_config(
        page_title="CLAMSer v1.0",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    with st.sidebar:
        st.title("CLAMSer v1.0")
        st.header("File Upload")
        uploaded_files = st.file_uploader(
            "Upload CLAMS Data Files",
            accept_multiple_files=True,
            type=['csv', 'txt'],
            key="main_file_uploader",
            on_change=lambda: st.session_state.update(
                analysis_triggered=False, data_loaded=False, lean_mass_map={}
            )
        )
        st.markdown("---")

        if st.session_state.get('data_loaded', False) and st.session_state.get('param_options'):
            st.header("Analysis Controls")
            ui.render_analysis_controls(st.session_state.param_options)

            st.markdown("---")
            st.subheader("Outlier Flagging")
            st.caption("Flag data points greater than 'n' standard deviations from the mean for each animal.")
            st.number_input(
                "Standard Deviation Threshold",
                min_value=0.0,
                max_value=10.0,
                value=3.0,
                step=0.5,
                key="sd_threshold",
                help="Set to 0 to disable outlier flagging."
            )

            st.markdown("---")
            with st.expander("Project Information, Methodology & Credits", expanded=False): # Renamed for clarity
                st.markdown(
                    """
                    **CLAMSer** is an open-source tool designed to accelerate the initial analysis of metabolic data from Columbus Instruments Oxymax CLAMS systems.
                    """
                )
                st.markdown("---")
                st.markdown(
                    """
                    **How It Works: Our Methodology**
                    
                    CLAMSer processes your data through a standardized pipeline:
                    1.  **Parsing & Tidying:** Reads each file, identifies the parameter, and transforms data into a tidy format.
                    2.  **Cumulative Conversion:** If a parameter name contains "ACC" (e.g., `FEED1 ACC`), the data is converted from cumulative to interval values.
                    3.  **Time Filtering:** Filters data to your selected analysis window.
                    4.  **Light/Dark Annotation:** Tags each measurement as "Light" or "Dark" based on your sidebar settings.
                    5.  **Outlier Flagging:** Flags data points outside the standard deviation threshold you set for each animal. These points are highlighted in the plot and counted in the summary table but are **not removed** from calculations.
                    6.  **Grouping & Normalization:** Applies your group assignments and normalization mode.
                    7.  **Summarization & Export:** Calculates final summary statistics for tables, charts, and export.
                    """
                )

    if not uploaded_files:
        ui.render_main_view()
        return

    if not st.session_state.get('data_loaded', False):
        with st.spinner("Parsing data files..."):
            (st.session_state.parsed_data,
             st.session_state.param_options,
             st.session_state.animal_ids) = ui.load_and_parse_files(uploaded_files)
        st.session_state.data_loaded = True
        if not st.session_state.param_options and uploaded_files:
            st.error("Upload Error: We couldn't find any valid CLAMS parameters in the uploaded files. Please check that the files are correctly formatted and contain a ':DATA' marker.")
        if 'group_assignments' not in st.session_state: st.session_state.group_assignments = {}
        if 'num_groups' not in st.session_state: st.session_state.num_groups = 1
        st.rerun()

    st.header("Analysis Workspace")

    with st.expander("Step 1: Setup Groups & Lean Mass", expanded=True):
        ui.render_group_assignment_ui(st.session_state.animal_ids)
        st.markdown("---")
        lean_mass_input = ui.render_lean_mass_ui()
        parsed_map, error_msg = processing.parse_lean_mass_data(lean_mass_input)
        if error_msg:
            st.error(f"Lean Mass Data Error: {error_msg}")
            st.session_state.lean_mass_map = {}
        else:
            if parsed_map != st.session_state.get('lean_mass_map', {}):
                st.session_state.lean_mass_map = parsed_map
                if parsed_map:
                    st.toast(f"Updated lean mass for {len(parsed_map)} animals.", icon="✅")

    st.markdown("---")
    st.header("Step 2: Generate Results")

    if st.button("Process & Analyze Data", type="primary"):
        st.session_state.analysis_triggered = True

    if st.session_state.get('analysis_triggered', False):
        selected_param = st.session_state.get("selected_parameter")
        time_window_option = st.session_state.get("time_window_option")
        light_start, light_end = st.session_state.get("light_start"), st.session_state.get("light_end")
        sd_threshold = st.session_state.get("sd_threshold")

        if selected_param and selected_param in st.session_state.parsed_data:
            df_processed = None 
            with st.spinner(f"Processing data for {selected_param}..."):
                base_df = st.session_state.parsed_data[selected_param].copy()
                is_cumulative = 'ACC' in selected_param.upper()
                if is_cumulative: base_df = processing.calculate_interval_data(base_df)
                df_filtered = processing.filter_data_by_time(base_df, time_window_option, st.session_state.get("custom_start"), st.session_state.get("custom_end"))
                df_annotated = processing.add_light_dark_cycle_info(df_filtered, light_start, light_end)
                df_flagged = processing.flag_outliers(df_annotated, sd_threshold)
                df_processed = processing.add_group_info(df_flagged, st.session_state.get('group_assignments', {}))
                
            normalization_mode = st.session_state.get("normalization_mode", "Absolute Values")
            df_normalized, missing_ids, norm_error = processing.apply_normalization(
                df_processed, normalization_mode, st.session_state.get('lean_mass_map', {})
            )

            if norm_error: st.warning(norm_error, icon="⚠️")
            if missing_ids: st.warning(f"Lean mass data not found for the following animals, which were excluded from normalization: {', '.join(missing_ids)}", icon="⚠️")

            if not df_normalized.empty:
                st.header("Analysis Results")
                st.session_state.summary_df_animal = processing.calculate_summary_stats_per_animal(df_normalized)
                key_metrics = processing.calculate_key_metrics(df_normalized)
                group_summary_df = processing.calculate_summary_stats_per_group(df_normalized)
                
                st.subheader(f"Key Metrics for {selected_param} ({normalization_mode})")
                col1, col2, col3 = st.columns(3)
                with col1: st.metric(label="Overall Average", value=key_metrics['Overall Average'])
                with col2: st.metric(label="Light Period Average", value=key_metrics['Light Average'])
                with col3: st.metric(label="Dark Period Average", value=key_metrics['Dark Average'])
                st.markdown("---")
                st.subheader(f"Group Averages for {selected_param}")
                bar_chart_fig = plotting.create_summary_bar_chart(group_summary_df, selected_param)
                st.plotly_chart(bar_chart_fig, use_container_width=True)

                st.markdown("---")
                st.subheader("Interactive Timeline Display Options")

                available_groups = sorted(df_normalized['group'].unique())
                selected_groups = st.multiselect(
                    "Select groups to display on the timeline:",
                    options=available_groups,
                    default=available_groups,
                    key="group_filter_multiselect"
                )

                df_for_timeline = df_normalized[df_normalized['group'].isin(selected_groups)]
                
                st.subheader(f"Interactive Timeline for {selected_param}")
                if not df_for_timeline.empty:
                    timeline_fig = plotting.create_timeline_chart(df_for_timeline, light_start, light_end, selected_param)
                    st.plotly_chart(timeline_fig, use_container_width=True)
                else:
                    st.info("No data to display for the selected groups. Please select at least one group in the filter above.")
                
                st.markdown("---")
                st.subheader("Summary Data Table (per Animal)")
                st.dataframe(st.session_state.summary_df_animal, use_container_width=True)

                # --- START: NEW EXPORT SECTION ---
                st.markdown("---")
                st.subheader("Step 3: Export Results")

                col1_exp, col2_exp = st.columns(2)

                with col1_exp:
                    # Check if the summary DataFrame exists and is not empty
                    if 'summary_df_animal' in st.session_state and not st.session_state.summary_df_animal.empty:
                        st.download_button(
                           label="📥 Export Summary Data (.csv)",
                           data=processing.convert_df_to_csv(st.session_state.summary_df_animal),
                           file_name=f"{selected_param}_summary_data.csv",
                           mime='text/csv',
                           key='download_summary',
                           help="Downloads the aggregated summary statistics table shown above."
                        )
                        st.caption("Contains the final Light/Dark/Total averages for each animal.")

                with col2_exp:
                     # Check if the processed DataFrame exists and is not empty
                    if not df_normalized.empty:
                        st.download_button(
                            label="🔬 Download Raw Data for Validation (.csv)",
                            data=validation_utils.generate_manual_validation_template(df_normalized),
                            file_name=f"{selected_param}_validation_data.csv",
                            mime='text/csv',
                            key='download_validation',
                            help="Downloads the full, point-by-point dataset used for all calculations."
                        )
                        st.caption("Ideal for manual validation in Excel or Prism.")
                # --- END: NEW EXPORT SECTION ---

            else:
                st.warning("No data remains to be displayed after processing and normalization.", icon="💡")
        else:
            st.info("Click 'Process & Analyze Data' to generate results.")

if __name__ == "__main__":
    main()