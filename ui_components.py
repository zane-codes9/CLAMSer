# ui_components.py

import streamlit as st
import pandas as pd
import processing

def load_and_parse_files(uploaded_files):
    """Parses all uploaded files and returns data, options, and animal IDs."""
    parsed_data = {}
    param_options = []
    all_animal_ids = set()
    
    for file in uploaded_files:
        try:
            file_content = file.getvalue().decode('utf-8', errors='ignore')
            lines = file_content.splitlines()
        except Exception as e:
            st.error(f"Could not read file {file.name}. Error: {e}")
            continue
        
        parameter, animal_ids_map, data_start_line = processing.parse_clams_header(lines)
        if parameter and data_start_line > -1:
            if parameter not in param_options:
                param_options.append(parameter)
            df_tidy = processing.parse_clams_data(lines, data_start_line, animal_ids_map)
            if df_tidy is not None and not df_tidy.empty:
                parsed_data[parameter] = df_tidy
                all_animal_ids.update(df_tidy['animal_id'].unique())
            else:
                st.warning(f"Could not parse data for parameter '{parameter}' in file '{file.name}'.")
                
    return parsed_data, sorted(param_options), sorted(list(all_animal_ids))


def render_analysis_controls(param_options):
    """Renders the analysis controls in the sidebar."""
    selected_parameter = st.selectbox(
        "Select Parameter to Analyze", options=param_options, key="selected_parameter"
    )
    time_window_option = st.selectbox(
        "Select Analysis Time Window",
        options=["Entire Dataset", "Last 24 Hours", "Last 48 Hours", "Last 72 Hours", "Custom..."],
        key="time_window_option"
    )
    custom_start, custom_end = None, None
    if time_window_option == "Custom...":
        col1, col2 = st.columns(2)
        with col1: custom_start = st.number_input("Start (hours from start)", min_value=0, step=1, key="custom_start")
        with col2: custom_end = st.number_input("End (hours from start)", min_value=custom_start or 0, step=1, key="custom_end")
    st.markdown("---")
    st.subheader("Light/Dark Cycle")
    light_start = st.slider("Light Cycle Start Hour (24h)", 0, 23, 7, key="light_start")
    light_end = st.slider("Light Cycle End Hour (24h)", 0, 23, 19, key="light_end")
    
    return {
        "selected_parameter": selected_parameter, "time_window_option": time_window_option,
        "custom_start": custom_start, "custom_end": custom_end,
        "light_start": light_start, "light_end": light_end,
    }

def render_main_view():
    """Renders the initial welcome/instruction view."""
    st.title("Welcome to CLAMSer v1.0")
    st.markdown("A tool for streamlined analysis of single-run CLAMS metabolic data.")
    st.info("To begin, please upload your CLAMS data files using the sidebar uploader.", icon="👈")


# --- START OF CHANGE ---
# The function no longer contains the expander.
def render_group_assignment_ui(all_animal_ids):
    """
    Renders the UI for group assignment, preventing duplicate assignments.
    This version uses st.form for a better user experience.
    """
    st.subheader("A. Group Assignment")
    
    # Initialize session state for the number of groups if it doesn't exist.
    if 'num_groups' not in st.session_state:
        st.session_state.num_groups = 1
    # Initialize session state for group assignments if it doesn't exist.
    if 'group_assignments' not in st.session_state:
        st.session_state.group_assignments = {}

    # We need to manage group names and selections inside the form logic
    with st.form(key='group_form'):
        st.session_state.num_groups = st.number_input(
            "Number of Groups", 
            min_value=1, 
            value=st.session_state.num_groups, 
            step=1
        )
        
        cols = st.columns(st.session_state.num_groups)
        
        # Temp dict to hold UI state before form submission
        ui_assignments = {}
        
        # Get all animals already assigned in the current state
        all_assigned_animals = {animal for members in st.session_state.group_assignments.values() for animal in members}

        for i in range(st.session_state.num_groups):
            with cols[i]:
                # Preserve existing group name or create a new one
                group_names = list(st.session_state.group_assignments.keys())
                group_name = st.text_input("Group Name", value=group_names[i] if i < len(group_names) else f"Group {i+1}", key=f"group_name_{i}")
                
                current_group_members = st.session_state.group_assignments.get(group_names[i] if i < len(group_names) else group_name, [])
                
                # Available animals are those not assigned to OTHER groups
                other_assigned_animals = all_assigned_animals - set(current_group_members)
                available_options = [aid for aid in all_animal_ids if aid not in other_assigned_animals]
                
                selected_animals = st.multiselect(
                    f"Select Animals for {group_name}",
                    options=sorted(available_options),
                    default=current_group_members,
                    key=f"ms_{i}"
                )
                
                if group_name.strip():
                    ui_assignments[group_name.strip()] = selected_animals
        
        submitted = st.form_submit_button("Update Groups")
        if submitted:
            # On submission, update the main session state with the form's state
            st.session_state.group_assignments = {k: v for k, v in ui_assignments.items() if k}
            st.toast("Group assignments updated!", icon="👍")
            # We don't need to return anything because we modify state directly
    
    # Return the currently stored group assignments
    return st.session_state.get('group_assignments', {})
# --- END OF CHANGE ---


def render_lean_mass_ui():
    """Renders the UI for lean mass input and returns the raw input for parsing."""
    st.subheader("B. Lean Mass Input (Optional)")
    st.radio("Input Method", ["File Upload", "Manual Entry"], key='lean_mass_input_method', horizontal=True)

    if st.session_state.lean_mass_input_method == "File Upload":
        st.file_uploader("Upload Lean Mass CSV", type=['csv', 'txt'], key='lean_mass_uploader')
        st.caption("Format: Two columns (`animal_id,lean_mass`) with no header.")
        st.code("456,20.1\n457,21.5", language="text")
        return st.session_state.get('lean_mass_uploader')
    else:
        st.text_area(
            "Paste data here", key='lean_mass_manual_text',
            help="Paste two columns from a spreadsheet, or type 'animal_id,mass' on each line.", height=150
        )
        return st.session_state.get('lean_mass_manual_text', '').strip()