# ui_components.py

import streamlit as st
import pandas as pd
import processing

def load_and_parse_files(uploaded_files):
    """Parses all uploaded files and returns data, options, and animal IDs."""
    parsed_data = {}
    param_options = []
    all_animal_ids = set()
    errors_found = False # <-- New flag to track if we should halt

    for file in uploaded_files:
        try:
            file_content = file.getvalue().decode('utf-8', errors='ignore')
            lines = file_content.splitlines()
        except Exception as e:
            st.error(f"Fatal Error: Could not read file **{file.name}**. Error: {e}")
            errors_found = True
            continue # Skip to the next file
        
        parameter, animal_ids_map, data_start_line = processing.parse_clams_header(lines)

        # --- START: THIS IS THE CRITICAL NEW LOGIC ---
        if parameter is None or data_start_line == -1:
            # parse_clams_header already prints its own specific st.error, so we
            # just add context and halt further processing for this file.
            st.warning(f"Skipping file **{file.name}** due to a header parsing error. Check that it is a valid, unmodified CLAMS file.")
            errors_found = True
            continue
        # --- END: CRITICAL NEW LOGIC ---

        if parameter not in param_options:
            param_options.append(parameter)
        
        df_tidy = processing.parse_clams_data(lines, data_start_line, animal_ids_map)
        
        if df_tidy is not None and not df_tidy.empty:
            parsed_data[parameter] = df_tidy
            all_animal_ids.update(df_tidy['animal_id'].unique())
        else:
            # This catches failures in the data section parsing
            st.error(f"Failed to extract data from **{file.name}** for parameter '{parameter}'. The file may be corrupt or formatted incorrectly after the ':DATA' marker.")
            errors_found = True

    # If any error was found, we should not proceed with a potentially incomplete dataset
    if errors_found:
        st.stop() # Halts the script to ensure user sees the errors.

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

def render_mass_ui(mass_type_label: str, key_prefix: str, help_text: str):
    """
    Renders a generic UI for mass data input (e.g., Body Weight, Lean Mass).
    
    Args:
        mass_type_label (str): The label for the subheader (e.g., "Body Weight").
        key_prefix (str): A unique prefix for Streamlit keys (e.g., "bw", "lm").
        help_text (str): Specific help text for the user.
    """
    st.subheader(f"{mass_type_label} Input (Optional)")
    
    # Use unique keys for each instance of this UI component
    radio_key = f"{key_prefix}_input_method"
    uploader_key = f"{key_prefix}_uploader"
    manual_text_key = f"{key_prefix}_manual_text"

    st.radio(
        "Input Method", 
        ["File Upload", "Manual Entry"], 
        key=radio_key, 
        horizontal=True
    )

    if st.session_state[radio_key] == "File Upload":
        st.file_uploader(f"Upload {mass_type_label} CSV", type=['csv', 'txt'], key=uploader_key)
        st.caption(f"Format: Two columns (`animal_id,{key_prefix}_mass`) with no header.")
        st.code(f"456,25.3\n457,24.1", language="text") # Example with a different value
        return st.session_state.get(uploader_key)
    else:
        st.text_area(
            "Paste data here", 
            key=manual_text_key,
            help=help_text, 
            height=150
        )
        return st.session_state.get(manual_text_key, '').strip()