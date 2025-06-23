# ui_components.py

import streamlit as st
import pandas as pd

def render_analysis_controls(param_options):
    """
    Renders the analysis controls that appear AFTER files are uploaded.
    This function assumes it is called inside an `st.sidebar` context.
    """
    selected_parameter = st.selectbox(
        "Select Parameter to Analyze",
        options=param_options,
        key="selected_parameter"
    )
    time_window_option = st.selectbox(
        "Select Analysis Time Window",
        options=["Entire Dataset", "Last 24 Hours", "Last 48 Hours", "Last 72 Hours", "Custom..."],
        key="time_window_option"
    )
    custom_start = None
    custom_end = None
    if time_window_option == "Custom...":
        col1, col2 = st.columns(2)
        with col1:
            custom_start = st.number_input("Start (hours from start)", min_value=0, step=1, key="custom_start")
        with col2:
            custom_end = st.number_input("End (hours from start)", min_value=custom_start or 0, step=1, key="custom_end")
    st.markdown("---")
    st.subheader("Light/Dark Cycle")
    light_start = st.slider("Light Cycle Start Hour (24h)", 0, 23, 7, key="light_start")
    light_end = st.slider("Light Cycle End Hour (24h)", 0, 23, 19, key="light_end")
    return {
        "selected_parameter": selected_parameter,
        "time_window_option": time_window_option,
        "custom_start": custom_start,
        "custom_end": custom_end,
        "light_start": light_start,
        "light_end": light_end,
    }


def render_main_view():
    """Renders the main content area of the application."""
    st.header("CLAMSer")
    st.write("Start by uploading your CLAMS data files using the sidebar.")
    st.info("Once files are uploaded, configure your analysis using the controls on the left.")


def render_setup_expander(all_animal_ids):
    """
    Renders the UI for group assignment AND lean mass input.
    """
    # Initialize session state keys
    if 'group_assignments' not in st.session_state:
        st.session_state.group_assignments = {}
    if 'num_groups' not in st.session_state:
        st.session_state.num_groups = 1
    if 'lean_mass_input_method' not in st.session_state:
        st.session_state.lean_mass_input_method = "File Upload"

    with st.expander("Step 1: Setup Groups & Lean Mass", expanded=True):
        # --- A. Group Assignment ---
        st.subheader("A. Group Assignment")
        num_groups = st.number_input("Number of Groups", min_value=1, value=st.session_state.num_groups, step=1)
        cols = st.columns(num_groups)
        temp_assignments = {}
        all_assigned_animals_map = {
            animal: group_name
            for group_name, animals in st.session_state.group_assignments.items()
            for animal in animals
        }
        for i in range(num_groups):
            with cols[i]:
                group_keys = list(st.session_state.group_assignments.keys())
                default_name = group_keys[i] if i < len(group_keys) else f"Group {i+1}"
                group_name = st.text_input("Group Name", value=default_name, key=f"group_name_{i}")
                members_of_this_group = st.session_state.group_assignments.get(default_name, [])
                selectable_options = members_of_this_group + [
                    animal for animal in all_animal_ids if animal not in all_assigned_animals_map
                ]
                selections = st.multiselect(
                    f"Select Animals for {group_name}",
                    options=sorted(list(set(selectable_options))),
                    default=members_of_this_group,
                    key=f"ms_{i}"
                )
                if group_name:
                    temp_assignments[group_name] = selections
        if st.button("Save Group Assignments"):
            st.session_state.num_groups = num_groups
            st.session_state.group_assignments = temp_assignments
            st.success("Group assignments saved!")
            st.rerun()

        st.markdown("---")

        # --- B. Lean Mass Input (Optional) ---
        st.subheader("B. Lean Mass Input (Optional)")
        st.write("Provide lean mass data if you plan to use 'Lean Mass Normalized' mode.")

        # Let user choose input method
        st.radio(
            "Lean Mass Input Method",
            options=["File Upload", "Manual Entry"],
            key='lean_mass_input_method',
            horizontal=True
        )

        if st.session_state.lean_mass_input_method == "File Upload":
            st.file_uploader(
                "Upload Lean Mass CSV",
                type=['csv', 'txt'],
                key='lean_mass_uploader' # This key will hold the uploaded file
            )
            with st.expander("CSV Format Instructions"):
                st.markdown("""
                - The file must be a CSV with two columns: `animal_id`, `lean_mass` (in grams).
                - **Do not include a header row.**
                """)
                st.code("456,20.1\n457,21.5\n458,19.8", language="text")
        else: # Manual Entry
            st.text_area(
                "Paste data here (e.g., 'animal_id,lean_mass')",
                key='lean_mass_manual_text', # This key will hold the text
                help="Paste two columns from a spreadsheet, or type 'animal_id,mass' on each line.",
                height=150
            )