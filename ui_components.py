# ui_components.py

import streamlit as st

def render_analysis_controls(param_options):
    """
    Renders the analysis controls that appear AFTER files are uploaded.
    This function assumes it is called inside an `st.sidebar` context.

    Args:
        param_options (list): A list of parameter names parsed from the uploaded files.

    Returns:
        dict: A dictionary containing all the user's settings.
    """
    # 1. Parameter Selection
    selected_parameter = st.selectbox(
        "Select Parameter to Analyze",
        options=param_options,
        key="selected_parameter" # Add a key for stability
    )

    # 2. Time Window Selection
    time_window_option = st.selectbox(
        "Select Analysis Time Window",
        options=["Entire Dataset", "Last 24 Hours", "Last 48 Hours", "Last 72 Hours", "Custom..."],
        key="time_window_option"
    )
    # Conditional inputs for "Custom..."
    custom_start = None
    custom_end = None
    if time_window_option == "Custom...":
        col1, col2 = st.columns(2)
        with col1:
            custom_start = st.number_input("Start (hours from start)", min_value=0, step=1, key="custom_start")
        with col2:
            custom_end = st.number_input("End (hours from start)", min_value=custom_start or 0, step=1, key="custom_end")

    st.markdown("---")

    # 3. Light/Dark Cycle Configuration
    st.subheader("Light/Dark Cycle")
    light_start = st.slider("Light Cycle Start Hour (24h)", 0, 23, 7, key="light_start")
    light_end = st.slider("Light Cycle End Hour (24h)", 0, 23, 19, key="light_end")

    # --- Return all settings ---
    return {
        "selected_parameter": selected_parameter,
        "time_window_option": time_window_option,
        "custom_start": custom_start,
        "custom_end": custom_end,
        "light_start": light_start,
        "light_end": light_end,
    }


def render_main_view():
    """
    Renders the main content area of the application.
    "Workspace" where results are displayed.
    """
    st.header("CLAMSer")
    st.write("Start by uploading your CLAMS data files using the sidebar.")
    st.info("Once files are uploaded, configure your analysis using the controls on the left.")


def render_setup_expander(all_animal_ids):
    """
    Renders the UI for group assignment. Fixes logic to prevent overlap.
    """
    if 'group_assignments' not in st.session_state:
        st.session_state.group_assignments = {}
    if 'num_groups' not in st.session_state:
        st.session_state.num_groups = 1

    with st.expander("Step 1: Setup Groups & Lean Mass", expanded=True):
        st.subheader("Group Assignment")
        st.write("Define your experimental groups and assign animals to them. Click 'Save' to apply changes.")

        num_groups = st.number_input(
            "Number of Groups",
            min_value=1,
            value=st.session_state.num_groups,
            step=1
        )

        cols = st.columns(num_groups)
        temp_assignments = {}
        
        # Build a map of all animals that are currently assigned to a group
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

                # Animals that were in this group in the previous state
                members_of_this_group = st.session_state.group_assignments.get(default_name, [])
                
                # Available options = members of THIS group + any animal that is NOT in the master assigned list
                selectable_options = members_of_this_group + [
                    animal for animal in all_animal_ids if animal not in all_assigned_animals_map
                ]

                selections = st.multiselect(
                    f"Select Animals for {group_name}",
                    options=sorted(list(set(selectable_options))), # Use set to remove duplicates
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