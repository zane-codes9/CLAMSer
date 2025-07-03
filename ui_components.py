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
        st.caption("Filter data to a specific time of day (24-hr format).") # Add clarification
        col1, col2 = st.columns(2)
        # --- CHANGE LABELS FOR CLARITY ---
        with col1: custom_start = st.number_input("Start Hour", min_value=0, max_value=23, step=1, key="custom_start")
        with col2: custom_end = st.number_input("End Hour", min_value=0, max_value=23, step=1, key="custom_end")
    
    st.markdown("---")
    st.subheader("Light/Dark Cycle")
    
    # UI CLARIFICATION ---
    st.caption("Define the light period using 24-hour format. The time outside this range will be considered the dark period.")
    light_start = st.slider("Light Cycle START Hour", 0, 23, 7, key="light_start")
    light_end = st.slider("Light Cycle END Hour", 0, 23, 19, key="light_end")
    st.caption(f"Current setting: Light period is from {light_start}:00 to {light_end}:00.")

    return {
        "selected_parameter": selected_parameter, "time_window_option": time_window_option,
        "custom_start": custom_start, "custom_end": custom_end,
        "light_start": light_start, "light_end": light_end,
    }

def render_main_view():
    """Renders the initial welcome/instruction view."""
    st.title("Welcome to CLAMSer v1.0")
    st.markdown("A tool for the rapid analysis and visualization of metabolic data.")
    st.subheader("Designed for data from Columbus Instruments Oxymax-CLAMS systems.")
    st.info("To begin, please upload your CLAMS data files using the sidebar uploader.", icon="👈")

def _update_group_assignments_callback():
    """
    Callback function to read all group UI widgets and update session_state.
    This is the core of the new reactive logic.
    """
    num_groups = st.session_state.get('num_groups', 1)
    new_assignments = {}
    all_assigned_in_new_state = set()

    # First pass to build the new assignment dictionary and check for duplicates
    for i in range(num_groups):
        group_name_key = f"group_name_{i}"
        multiselect_key = f"ms_{i}"
        group_name = st.session_state.get(group_name_key, f"Group {i+1}").strip()
        selected_animals = st.session_state.get(multiselect_key, [])

        if group_name:
            # Check for animals already assigned in this new state
            for animal in selected_animals:
                if animal in all_assigned_in_new_state:
                    # This is a basic way to handle it; more complex UI could show a warning
                    st.warning(f"Animal '{animal}' cannot be in multiple groups. Reverting some changes.")
                    # To prevent inconsistent state, we might just return without updating
                    return
            
            new_assignments[group_name] = selected_animals
            all_assigned_in_new_state.update(selected_animals)
            
    st.session_state.group_assignments = new_assignments
    st.toast("Group assignments updated!", icon="👍")


def render_group_assignment_ui(all_animal_ids):
    """
    Renders a live, reactive UI for group assignment.
    Changes are captured instantly via callbacks, no 'Update' button needed.
    """
    st.subheader("A. Group Assignment")

    if 'num_groups' not in st.session_state: st.session_state.num_groups = 1
    if 'group_assignments' not in st.session_state: st.session_state.group_assignments = {}

    st.number_input(
        "Number of Groups",
        min_value=1,
        step=1,
        key='num_groups',
        on_change=_update_group_assignments_callback # This will trigger a re-build when number changes
    )

    num_groups = st.session_state.get('num_groups', 1)
    cols = st.columns(num_groups)

    # Get a snapshot of all animals assigned right now
    all_assigned_animals = {animal for members in st.session_state.group_assignments.values() for animal in members}

    for i in range(num_groups):
        with cols[i]:
            group_name_key = f"group_name_{i}"
            multiselect_key = f"ms_{i}"
            
            # Find the group name corresponding to this column index if it exists
            # This is complex because dict keys aren't ordered, but for UI it's often stable enough
            current_group_name = ""
            try:
                current_group_name = list(st.session_state.group_assignments.keys())[i]
            except IndexError:
                current_group_name = f"Group {i+1}"
            
            st.text_input(
                "Group Name",
                value=current_group_name,
                key=group_name_key,
                on_change=_update_group_assignments_callback
            )
            
            current_group_members = st.session_state.group_assignments.get(current_group_name, [])
            
            # Available animals = all animals - animals assigned to OTHER groups
            other_assigned_animals = all_assigned_animals - set(current_group_members)
            available_options = [aid for aid in all_animal_ids if aid not in other_assigned_animals]
            
            st.multiselect(
                "Select Animals",
                options=sorted(available_options),
                default=current_group_members,
                key=multiselect_key,
                on_change=_update_group_assignments_callback
            )
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