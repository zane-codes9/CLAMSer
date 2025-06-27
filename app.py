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
        st.title("🧬 CLAMSer v1.0")
        st.header("File Upload")
        uploaded_files = st.file_uploader(
            "Upload CLAMS Data Files",
            accept_multiple_files=True,
            type=['csv', 'txt'],
            key="main_file_uploader",
            on_change=lambda: st.session_state.update(
                analysis_triggered=False, 
                data_loaded=False, 
                lean_mass_map={}
            )
        )
        st.markdown("---")

        # --- START OF CHANGE ---
        # The logic for rendering the rest of the sidebar is now guarded.
        # It will ONLY appear after files have been uploaded and successfully parsed.
        if st.session_state.get('data_loaded', False) and st.session_state.get('param_options'):
            st.header("Analysis Controls")
            # This function now correctly receives a non-empty list of options.
            ui.render_analysis_controls(st.session_state.param_options)
            
            st.markdown("---")
            with st.expander("Project Information & Credits"):
                st.markdown(
                    """
                    **CLAMSer** is an open-source tool designed to accelerate the initial analysis of metabolic data from Columbus Instruments Oxymax CLAMS systems.
                    **Cite Us:** (Placeholder for DOI/Publication Info)
                    **Repository:** [GitHub](https://github.com/your-repo/clamser-v1)
                    **Built With:** Streamlit, Pandas, Plotly
                    """
                )
        # --- END OF CHANGE ---

    if not uploaded_files:
        ui.render_main_view()
        return

    # --- Initial Data Parsing ---
    # This block now runs first and populates session_state before the sidebar tries to render controls.
    if not st.session_state.get('data_loaded', False):
        with st.spinner("Parsing data files..."):
            (st.session_state.parsed_data, 
             st.session_state.param_options, 
             st.session_state.animal_ids) = ui.load_and_parse_files(uploaded_files)
        st.session_state.data_loaded = True
        
        # Initialize other state variables here
        if 'group_assignments' not in st.session_state: st.session_state.group_assignments = {}
        if 'num_groups' not in st.session_state: st.session_state.num_groups = 1
        if 'lean_mass_map' not in st.session_state: st.session_state.lean_mass_map = {}
        if 'analysis_triggered' not in st.session_state: st.session_state.analysis_triggered = False
        st.rerun() # Rerun to make the new sidebar controls appear.

    if not st.session_state.param_options:
        st.warning("No valid CLAMS data could be parsed. Please check your file formats.")
        return

    # --- Main Workspace (The rest of the file remains unchanged) ---
    analysis_settings = {
        "selected_parameter": st.session_state.get("selected_parameter"),
        "time_window_option": st.session_state.get("time_window_option"),
        "custom_start": st.session_state.get("custom_start"),
        "custom_end": st.session_state.get("custom_end"),
        "light_start": st.session_state.get("light_start"),
        "light_end": st.session_state.get("light_end"),
    }
    
    st.header("Analysis Workspace")
    
    with st.expander("How It Works: Our Methodology", expanded=False):
        # ... (content is unchanged)
        st.markdown(
            """
            CLAMSer processes your data through a standardized, transparent pipeline to ensure reproducibility and clarity. Here are the steps:

            1.  **Parsing & Tidying:** The application reads each uploaded file, automatically identifies the parameter (e.g., VO2, RER), and extracts the animal IDs. It then transforms the data from the wide format (one column per animal) into a "tidy" long format, where each row represents a single measurement for a single animal.
            2.  **Time Filtering:** Based on your selection in the sidebar ("Entire Dataset", "Last 24 Hours", etc.), the data is filtered to include only the relevant time window for analysis.
            3.  **Light/Dark Annotation:** Each measurement is tagged as belonging to either the "Light" or "Dark" period according to the cycle hours you define in the sidebar.
            4.  **Grouping & Normalization:** Your custom group assignments are added to the data. If you select a normalization mode, the 'value' for each measurement is adjusted (e.g., divided by the corresponding animal's lean mass).
            5.  **Summarization & Export:** With the processed data ready, the application calculates the final summary statistics (averages for Light, Dark, and Total periods) that you see in the tables and charts below. The exported data provides these final summaries, while the validation file provides the data from Step 4.
            """
        )
    
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

    # ... The rest of app.py is identical
    with st.expander("Sanity Check: Live Group Assignments"):
        st.json(st.session_state.get('group_assignments', {}))

    st.markdown("---")
    st.header("Step 2: Generate Results")

    if st.button("Process & Analyze Data", type="primary"):
        st.session_state.analysis_triggered = True
        selected_param = analysis_settings.get("selected_parameter")
        if selected_param and selected_param in st.session_state.parsed_data:
            with st.spinner("Processing time filters and annotating data..."):
                base_df = st.session_state.parsed_data[selected_param].copy()
                df_filtered = processing.filter_data_by_time(base_df, analysis_settings["time_window_option"], analysis_settings["custom_start"], analysis_settings["custom_end"])
                df_processed = processing.add_light_dark_cycle_info(df_filtered, analysis_settings["light_start"], analysis_settings["light_end"])
                st.session_state.df_processed_for_display = df_processed
        else:
            st.session_state.df_processed_for_display = pd.DataFrame()
            st.session_state.analysis_triggered = False
            st.error("Could not find data for the selected parameter. Please re-check.")

    if st.session_state.get('analysis_triggered', False):
        st.header("Analysis Results")
        
        normalization_mode = st.radio(
            "Select Normalization Mode",
            options=["Absolute Values", "Body Weight Normalized", "Lean Mass Normalized"],
            key="normalization_mode",
            horizontal=True
        )
    
        df_base_processed = st.session_state.get('df_processed_for_display', pd.DataFrame())
        
        if not df_base_processed.empty:
            df_with_groups = processing.add_group_info(df_base_processed, st.session_state.get('group_assignments', {}))
            df_normalized, missing_ids, norm_error = processing.apply_normalization(
                df_with_groups, 
                normalization_mode, 
                st.session_state.get('lean_mass_map', {})
            )
            if norm_error: st.warning(norm_error, icon="⚠️")
            if missing_ids: st.info(f"The following animals were excluded from '{normalization_mode}' analysis due to missing data: {', '.join(map(str, missing_ids))}", icon="ℹ️")

            if not df_normalized.empty:
                selected_param = analysis_settings.get("selected_parameter")
                key_metrics = processing.calculate_key_metrics(df_normalized)
                st.subheader(f"Key Metrics for {selected_param} ({normalization_mode})")
                col1, col2, col3 = st.columns(3)
                with col1: st.metric(label="Overall Average", value=key_metrics['Overall Average'])
                with col2: st.metric(label="Light Period Average", value=key_metrics['Light Average'])
                with col3: st.metric(label="Dark Period Average", value=key_metrics['Dark Average'])
                st.markdown("---")

                st.subheader(f"Group Averages for {selected_param}")
                group_summary_df = processing.calculate_summary_stats_per_group(df_normalized)
                bar_chart_fig = plotting.create_summary_bar_chart(group_summary_df, selected_param)
                st.plotly_chart(bar_chart_fig, use_container_width=True)

                st.subheader(f"Interactive Timeline for {selected_param}")
                timeline_fig = plotting.create_timeline_chart(df_normalized, analysis_settings['light_start'], analysis_settings['light_end'], selected_param)
                st.plotly_chart(timeline_fig, use_container_width=True)
                
                st.markdown("---")
                st.subheader("Summary Data Table (per Animal)")
                summary_df_animal = processing.calculate_summary_stats_per_animal(df_normalized)
                st.dataframe(summary_df_animal, use_container_width=True)
                
                st.download_button(
                   label="⬇️ Export Summary Data (.csv)",
                   data=processing.convert_df_to_csv(summary_df_animal),
                   file_name=f"CLAMSer_Summary_{selected_param}_{normalization_mode.replace(' ', '_')}.csv",
                   mime='text/csv',
                )

                st.markdown("---")
                with st.expander("Internal Validation & Raw Data Export"):
                    st.info(
                        """
                        This section allows you to download the data **after** it has been filtered, annotated, and normalized, but **before** any averaging or summary statistics are calculated.
                        
                        This is the exact dataset used to generate the charts and tables above. You can use this file in Excel, Prism, or any other software to manually verify the summary calculations.
                        """,
                        icon="✅"
                    )

                    validation_csv = validation_utils.generate_manual_validation_template(df_normalized)

                    st.download_button(
                        label="⬇️ Download Pre-Summary Data for Manual Validation (.csv)",
                        data=validation_csv,
                        file_name=f"CLAMSer_Validation_Data_{selected_param}_{normalization_mode.replace(' ', '_')}.csv",
                        mime='text/csv',
                    )
                    
                    with st.container(border=True):
                        st.write("**Sanity Check: First 20 rows of the validation data to be exported:**")
                        st.dataframe(df_normalized[['animal_id', 'group', 'period', 'value']].head(20), use_container_width=True)

            else:
                st.warning("No data remains to be displayed. This can happen if no animals in the dataset have corresponding lean mass data.", icon="💡")
        else:
            st.warning("No data to display. Please click 'Process & Analyze Data' first.")

if __name__ == "__main__":
    main()