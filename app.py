import streamlit as st
import ui
import processing

def main():
    """
    Main function to run the Streamlit application.
    """
    # 1. Set page configuration (must be the first Streamlit command)
    st.set_page_config(
        page_title="CLAMSer v1.0",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 2. Render the UI components
    ui.render_sidebar()
    ui.render_main_view()

    # 3. (Future) Call the processing pipeline based on user actions
    # For now, this does nothing but serves as a placeholder for the workflow.
    # summary_df, chart_data, timeline_data = processing.run_analysis_pipeline()


if __name__ == "__main__":
    main()