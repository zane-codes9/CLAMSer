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
            type=['csv'],
            key="main_file_uploader",
            on_change=lambda: st.session_state.update(
                run_analysis=False, data_loaded=False, body_weight_map={}, lean_mass_map={}
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
                value=st.session_state.get("sd_threshold", 3.0),
                step=0.5,
                key="sd_threshold",
                help="Set to 0 to disable outlier flagging."
            )

            st.markdown("---")
            with st.expander("Project Information, Methodology & Credits", expanded=False):
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

    # --- CHANGE: This now calls our new, more informative welcome screen ---
    if not uploaded_files:
        ui.render_main_view()
        return

    # --- Data Loading and Initial State Setup ---
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

    # ==============================================================================
    # --- START OF NEW "THREE-STEP WORKFLOW" LAYOUT ---
    # ==============================================================================

    # --- STEP 1: SETUP ---
    st.header("Step 1: Setup Groups & Mass Data")
    st.caption("Define your experimental groups and provide mass data for normalization.")

    # We now use targeted expanders within Step 1 for better organization
    setup_expander_expanded_state = not st.session_state.get('run_analysis', False)

    with st.expander("Assign Experimental Groups", expanded=setup_expander_expanded_state):
        ui.render_group_assignment_ui(st.session_state.animal_ids)

    with st.expander("Provide Mass Data & Confirm Parsing (Optional)", expanded=setup_expander_expanded_state):
        col1_mass, col2_mass = st.columns(2)
        with col1_mass:
            bw_input = ui.render_mass_ui("Body Weight", "bw", "Paste two columns: animal_id, body_weight")
            parsed_bw_map, bw_error_msg = processing.parse_mass_data(bw_input, "body weight")
            if bw_error_msg: st.error(f"Body Weight Data Error: {bw_error_msg}")
            elif parsed_bw_map is not None and parsed_bw_map != st.session_state.get('body_weight_map', {}):
                st.session_state.body_weight_map = parsed_bw_map
                if parsed_bw_map: st.toast(f"Updated body weight for {len(parsed_bw_map)} animals.", icon="⚖️")

        with col2_mass:
            lm_input = ui.render_mass_ui("Lean Mass", "lm", "Paste two columns: animal_id, lean_mass")
            parsed_lm_map, lm_error_msg = processing.parse_mass_data(lm_input, "lean mass")
            if lm_error_msg: st.error(f"Lean Mass Data Error: {lm_error_msg}")
            elif parsed_lm_map is not None and parsed_lm_map != st.session_state.get('lean_mass_map', {}):
                st.session_state.lean_mass_map = parsed_lm_map
                if parsed_lm_map: st.toast(f"Updated lean mass for {len(parsed_lm_map)} animals.", icon="💪")
        
        # --- MERGED: The confirmation is now part of the mass input step ---
        st.markdown("---")
        st.write("**Parsed Mass Data Confirmation:**")
        
        bw_map = st.session_state.get('body_weight_map', {})
        if bw_map: st.json({"Body Weight Data Found": bw_map})
        else: st.caption("⚪ Body Weight Data: Not provided.")

        lm_map = st.session_state.get('lean_mass_map', {})
        if lm_map: st.json({"Lean Mass Data Found": lm_map})
        else: st.caption("⚪ Lean Mass Data: Not provided.")

    # --- STEP 2: PROCESS ---
    st.markdown("---")
    st.header("Step 2: Process & Review Results")
    st.caption("Once your setup is complete, click the button below to generate your results.")
    
    if st.button("Process & Analyze Data", type="primary", use_container_width=True, help="Click to run the analysis based on the settings configured above and in the sidebar."):
        st.session_state.run_analysis = True
        st.rerun() # CHANGE: Force an immediate rerun to collapse the Step 1 expanders and render results.

    # --- RESULTS AREA (Conditional on Processing) ---
    if st.session_state.get('run_analysis', False):
        st.radio(
            "**Normalization Mode**",
            options=["Absolute Values", "Body Weight Normalized", "Lean Mass Normalized"],
            key="normalization_mode", horizontal=True,
        )
        st.markdown("---")

        selected_param = st.session_state.get("selected_parameter")
        if selected_param and selected_param in st.session_state.parsed_data:
            with st.spinner(f"Processing data for {selected_param}..."):
                # Full processing pipeline...
                base_df = st.session_state.parsed_data[selected_param].copy()
                is_cumulative = 'ACC' in selected_param.upper()
                if is_cumulative: base_df = processing.calculate_interval_data(base_df)
                df_filtered = processing.filter_data_by_time(base_df, st.session_state.get("time_window_option"), st.session_state.get("custom_start"), st.session_state.get("custom_end"))
                df_annotated = processing.add_light_dark_cycle_info(df_filtered, st.session_state.get("light_start"), st.session_state.get("light_end"))
                df_flagged = processing.flag_outliers(df_annotated, st.session_state.get("sd_threshold"))
                df_processed = processing.add_group_info(df_flagged, st.session_state.get('group_assignments', {}))
            
            normalization_mode = st.session_state.get("normalization_mode", "Absolute Values")
            st.success(f"Displaying results for **{selected_param}** with **{normalization_mode}**.")

            df_normalized, missing_ids, norm_error = processing.apply_normalization(
                df_processed, normalization_mode, st.session_state.get('body_weight_map', {}), st.session_state.get('lean_mass_map', {}))

            if norm_error: st.warning(norm_error, icon="⚠️")
            if missing_ids:
                mass_type = "body weight" if "Body Weight" in normalization_mode else "lean mass"
                st.warning(f"No {mass_type} data found for: {', '.join(map(str, missing_ids))}", icon="⚠️")

            if not df_normalized.empty:
                st.session_state.summary_df_animal = processing.calculate_summary_stats_per_animal(df_normalized)
                key_metrics = processing.calculate_key_metrics(df_normalized)
                group_summary_df = processing.calculate_summary_stats_per_group(df_normalized)
                
                # --- Key Metrics Display ---
                st.subheader(f"Key Metrics for {selected_param} ({normalization_mode})")
                c1, c2, c3 = st.columns(3)
                c1.metric("Overall Average", key_metrics['Overall Average'])
                c2.metric("Light Period Average", key_metrics['Light Average'])
                c3.metric("Dark Period Average", key_metrics['Dark Average'])
                st.markdown("---")
                
                # --- Group Summary Plot ---
                st.subheader(f"Group Averages for {selected_param}")
                st.plotly_chart(plotting.create_summary_bar_chart(group_summary_df, selected_param), use_container_width=True)
                st.markdown("---")
                
                # --- Timeline Plot ---
                st.subheader("Interactive Timeline Display Options")
                available_groups = sorted(df_normalized['group'].unique())
                selected_groups = st.multiselect("Filter groups on timeline:", available_groups, default=available_groups)
                df_for_timeline = df_normalized[df_normalized['group'].isin(selected_groups)]
                st.subheader(f"Interactive Timeline for {selected_param}")
                if not df_for_timeline.empty:
                    st.plotly_chart(plotting.create_timeline_chart(df_for_timeline, st.session_state.light_start, st.session_state.light_end, selected_param), use_container_width=True)
                else:
                    st.info("Select at least one group to display its timeline.")
                st.markdown("---")
                
                # --- Summary Table ---
                st.subheader("Summary Data Table (per Animal)")
                st.dataframe(st.session_state.summary_df_animal, use_container_width=True)
                st.markdown("---")

                # --- STEP 3: EXPORT (Appears here, at the end of results) ---
                st.header("Step 3: Export Your Results")
                st.caption("Download summary data for statistical software, or the full processed dataset for manual validation.")
                c1_exp, c2_exp = st.columns(2)
                with c1_exp:
                    st.download_button(
                        label="📥 Export Summary Data (.csv)", data=processing.convert_df_to_csv(st.session_state.summary_df_animal),
                        file_name=f"{selected_param}_summary_data.csv", mime='text/csv', use_container_width=True)
                with c2_exp:
                    st.download_button(
                        label="🔬 Download Raw Data for Validation (.csv)", data=validation_utils.generate_manual_validation_template(df_normalized),
                        file_name=f"{selected_param}_validation_data.csv", mime='text/csv', use_container_width=True)
            else:
                st.warning("No data remains to be displayed after processing and normalization.", icon="💡")
        else:
            st.error(f"Parameter '{selected_param}' not found. Please select a valid parameter.")


if __name__ == "__main__":
    main()