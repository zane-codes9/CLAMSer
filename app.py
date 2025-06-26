# app.py

import streamlit as st
import pandas as pd
import ui_components as ui
import processing
import plotting

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

    if not uploaded_files:
        ui.render_main_view()
        return

    # --- Initial Data Parsing ---
    if not st.session_state.get('data_loaded', False):
        with st.spinner("Parsing data files..."):
            (st.session_state.parsed_data, 
             st.session_state.param_options, 
             st.session_state.animal_ids) = ui.load_and_parse_files(uploaded_files)
        st.session_state.data_loaded = True
        st.info(f"Parsed {len(st.session_state.param_options)} parameter(s) for {len(st.session_state.animal_ids)} animals.")
        # Initialize necessary session state keys
        if 'group_assignments' not in st.session_state: st.session_state.group_assignments = {}
        if 'num_groups' not in st.session_state: st.session_state.num_groups = 1
        if 'lean_mass_map' not in st.session_state: st.session_state.lean_mass_map = {}
        if 'analysis_triggered' not in st.session_state: st.session_state.analysis_triggered = False

    if not st.session_state.param_options:
        st.warning("No valid CLAMS data could be parsed. Please check your file formats.")
        return

    # --- Sidebar Controls ---
    with st.sidebar:
        st.header("Analysis Controls")
        analysis_settings = ui.render_analysis_controls(st.session_state.param_options)

    # --- Main Workspace Setup ---
    st.header("Analysis Workspace")
    
    # --- START OF CHANGE ---
    # The Setup expander now only contains the UI functions
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

    # The Group Assignment sanity check is now here, at the top level, not nested.
    with st.expander("Sanity Check: Current Group Assignments"):
        st.write("This shows the groups that will be used when you click 'Process & Analyze Data'. It updates after you click 'Update Groups' above.")
        st.json(st.session_state.get('group_assignments', {}))
    # --- END OF CHANGE ---

    st.markdown("---")
    st.header("Step 2: Configure & Generate Results")

    if st.button("Process & Analyze Data", type="primary"):
        st.session_state.analysis_triggered = True
        # Note: We no longer need to pass group assignments from the UI.
        # The button now signals that the analysis should use the latest assignments from session_state.
        selected_param = analysis_settings.get("selected_parameter")
        if selected_param and selected_param in st.session_state.parsed_data:
            with st.spinner("Processing time filters and annotating data..."):
                base_df = st.session_state.parsed_data[selected_param].copy()
                df_filtered = processing.filter_data_by_time(base_df, analysis_settings["time_window_option"], analysis_settings["custom_start"], analysis_settings["custom_end"])
                df_processed = processing.add_light_dark_cycle_info(df_filtered, analysis_settings["light_start"], analysis_settings["light_end"])
                st.session_state.df_processed_for_display = df_processed
        else:
            st.session_state.df_processed_for_display = pd.DataFrame()

    normalization_mode = st.radio(
        "Select Normalization Mode",
        options=["Absolute Values", "Body Weight Normalized", "Lean Mass Normalized"],
        key="normalization_mode",
        horizontal=True
    )
    
    if st.session_state.get('analysis_triggered', False):
        st.header("Analysis Results")
        
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

            with st.expander("Sanity Check: Reactive Normalization Flow"):
                st.write("**Current Normalization Mode:**", f"`{normalization_mode}`")
                st.write("**Lean Mass Data in Memory:**", st.session_state.get('lean_mass_map'))
                st.write("**Shape of DataFrame post-normalization:**", df_normalized.shape)
                
                if not df_normalized.empty:
                    st.write("**First 20 Rows of Final Normalized Data:**")
                    st.dataframe(df_normalized[['animal_id', 'group', 'timestamp', 'period', 'value']].head(20))
                else:
                    st.info("The final dataframe is empty, so no rows can be shown.")
            
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
            else:
                st.warning("No data remains to be displayed. This can happen if no animals in the dataset have corresponding lean mass data.", icon="💡")
        else:
            st.warning("No data to display. Please click 'Process & Analyze Data' first.")

if __name__ == "__main__":
    main()