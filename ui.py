import streamlit as st

def render_sidebar():
    """
    Renders the sidebar with all its components.
    This is the "Control Panel" of the app.
    """
    with st.sidebar:
        st.title("🧬 CLAMSer v1.0")
        st.header("Analysis Controls")
        st.write("Controls for file upload, time selection, and cycles will go here.")


def render_main_view():
    """
    Renders the main content area of the application.
    This is the "Workspace" where results are displayed.
    """
    st.header("CLAMSer: The Bridge from Raw Data to Analysis")
    st.write("Welcome! Start by uploading your CLAMS data files using the sidebar.")