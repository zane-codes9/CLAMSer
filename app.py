import streamlit as st
import ui
import processing

def main():
    """
    Main function to run the Streamlit application.
    """
    st.set_page_config(
        page_title="CLAMSer v1.0",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # In Streamlit, the script runs top-to-bottom on every interaction.
    # We get the state of the UI widgets first.
    uploaded_files = ui.render_sidebar()
    ui.render_main_view() # This just draws the static welcome message for now

    # Now, we check if the user has taken an action, e.g., uploaded files.
    if uploaded_files:
        st.header("File Header Verification")
        st.write("Parsing the header of each uploaded file...")

        # Process each file individually and show its header info
        for file in uploaded_files:
            parameter, animal_ids, data_start_line = processing.parse_clams_header(file)

            with st.expander(f"**File:** `{file.name}`"):
                if parameter:
                    st.success(f"**Parameter:** {parameter}")
                else:
                    st.error("Could not identify the parameter from the header.")

                if animal_ids:
                    st.success(f"**Animals Found:** {len(animal_ids)}")
                    st.json(animal_ids)
                else:
                    st.error("Could not find animal IDs.")

                if data_start_line != -1:
                    st.success(f"Data section starts on line **{data_start_line}**.")
                else:
                    st.error("Could not find the ':DATA' marker.")

if __name__ == "__main__":
    main()