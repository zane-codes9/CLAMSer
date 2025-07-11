# ui_components.py

import streamlit as st
import pandas as pd
import processing

def load_and_parse_files(uploaded_files):
    """
    Parses all uploaded files. Silently ignores non-data files and reports
    on files that look like data but fail to parse.
    """
    parsed_data = {}
    param_options = []
    all_animal_ids = set()
    files_with_parsing_errors = [] # To store names of files that failed after a successful header parse

    for file in uploaded_files:
        try:
            # First-pass filter: Only attempt to read CSV files.
            if not file.name.lower().endswith('.csv'):
                continue # Silently skip non-csv files like .PDTA, .ELOG, etc.

            file_content = file.getvalue().decode('utf-8', errors='ignore')
            lines = file_content.splitlines()
        except Exception as e:
            # This is a file-read error, worth mentioning.
            files_with_parsing_errors.append(f"{file.name} (could not be read: {e})")
            continue

        # Step 1: Attempt to parse the header.
        parameter, animal_ids_map, data_start_line = processing.parse_clams_header(lines)

        # Condition for silent ignore: If a file doesn't have the :DATA marker,
        # it's not a CLAMS data file we're interested in. Just skip it.
        if data_start_line == -1:
            continue

        # Condition for a warning: If it has :DATA but no parameter, it's malformed.
        if parameter is None:
            files_with_parsing_errors.append(f"{file.name} (has a ':DATA' marker but no 'Paramter' line was found)")
            continue
        
        # If we got this far, the header is valid. Now parse the data table.
        df_tidy = processing.parse_clams_data(lines, data_start_line, animal_ids_map)
        
        if df_tidy is not None and not df_tidy.empty:
            if parameter not in param_options:
                param_options.append(parameter)
            parsed_data[parameter] = df_tidy
            all_animal_ids.update(df_tidy['animal_id'].unique())
        else:
            # This file had a valid header but its data section failed to parse. This is a legitimate issue to report.
            files_with_parsing_errors.append(f"{file.name} (header was OK, but data table could not be parsed)")

    # --- Sanity Check: Report on files that failed parsing ---
    if files_with_parsing_errors:
        st.warning(
            "Some files looked like data but were skipped due to formatting errors:",
            icon="⚠️"
        )
        with st.expander("Click to see details on skipped files"):
            for failed_file in files_with_parsing_errors:
                st.caption(f"- {failed_file}")
    # --- End Sanity Check ---

    # After attempting to parse all files, check if we found anything usable.
    if not parsed_data:
        st.error(
            "Upload Error: We couldn't find any valid CLAMS data in the uploaded files. "
            "Please ensure you've uploaded the correct parameter CSV files (e.g., VO2.csv, RER.csv) "
            "and that they have not been modified.",
            icon="🚨"
        )
        st.stop() # Halt the script if no data was loaded at all.

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
        st.caption("Define a precise analysis window based on hours from the start of the experiment.")
        st.caption("Example: To skip the first 24h of acclimation in a 72h run, set Start to `24` and End to `72`.")
        col1, col2 = st.columns(2)
        with col1:
            custom_start = st.number_input(
                "Analysis Start (hours from exp. start)", 
                min_value=0.0, 
                value=0.0, 
                step=1.0, 
                key="custom_start"
            )
        with col2:
            custom_end = st.number_input(
                "Analysis End (hours from exp. start)", 
                min_value=0.0, 
                value=72.0, 
                step=1.0, 
                key="custom_end"
            )
    
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
    """
    Renders the initial welcome view, outlining the three-step workflow.
    This new view sets the user's expectation of the app's simplicity and process.
    """
    st.title("CLAMSer v2.0: Your Analysis in Three Steps")
    st.markdown("---")

    # --- Step 1 Description ---
    st.header("Step 1: Setup Groups & Mass Data")
    st.caption(
        "After uploading your raw CSV files in the sidebar, this section will appear. "
        "Here you will define your experimental groups and, optionally, provide body weight or lean mass values for normalization."
    )
    st.markdown("---")

    # --- Step 2 Description ---
    st.header("Step 2: Process & Review Results")
    st.caption(
        "After your setup is complete, you will click the main 'Process' button. "
        "This will generate interactive charts, key metrics, and summary data tables for your review."
    )
    st.markdown("---")

    # --- Step 3 Description ---
    st.header("Step 3: Export Your Results")
    st.caption(
        "Once the results are generated, you can download your clean, aggregated summary data as a CSV file. "
        "This file is formatted for direct use in Prism, SPSS, or your preferred statistical software."
    )
    st.markdown("---")
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
                    st.warning(f"Animal '{animal}' cannot be in multiple groups. Reverting some changes.")
                    # To prevent inconsistent state, no update
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
    st.subheader("Assign Animals to Experimental Groups")
    st.caption("Define your groups below. Animals not assigned to any group will be labeled 'Unassigned'.")

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

def render_mass_ui(mass_type_label: str, key_prefix: str, help_text: str):
    """
    Renders a generic UI for mass data input (e.g., Body Weight, Lean Mass).
    
    Args:
        mass_type_label (str): The label for the subheader (e.g., "Body Weight").
        key_prefix (str): A unique prefix for Streamlit keys (e.g., "bw", "lm").
        help_text (str): Specific help text for the user.
    """
    st.subheader(f"{mass_type_label} Input (Optional)")
    st.caption(f"Provide {mass_type_label.lower()} data by either uploading a CSV file or pasting values directly.")
    
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
        st.file_uploader(f"Upload {mass_type_label} CSV", type=['csv'], key=uploader_key)
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