import streamlit as st

def render_sidebar():
    """
    Renders the sidebar with all its components.
    This is the "Control Panel" of the app.
    This function now returns the uploaded files.
    """
    with st.sidebar:
        st.title("🧬 CLAMSer v1.0")
        st.header("Analysis Controls")

        # The uploader to allow multiple files
        uploaded_files = st.file_uploader(
            "Upload CLAMS Data Files",
            accept_multiple_files=True,
            type=['csv', 'txt']
        )

        st.markdown("---")
        st.info(
            "**Instructions:**\n"
            "1. Upload one or more raw data files from your CLAMS run.\n"
            "2. More controls will appear here as we build them."
        )

    return uploaded_files


def render_main_view():
    """
    Renders the main content area of the application.
    "Workspace" where results are displayed.
    """
    st.header("CLAMSer")
    st.write("Start by uploading your CLAMS data files using the sidebar.")