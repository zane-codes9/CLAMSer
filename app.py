import streamlit as st
import ui
import processing
import io  # <-- This is the line we are adding

def main():
    """
    Main function to run the Streamlit application.
    """
    st.set_page_config(
        page_title="CLAMSer v1.0",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    uploaded_files = ui.render_sidebar()
    ui.render_main_view()

    if uploaded_files:
        st.header("File Processing Results")
        
        # We will process and display one file at a time for clarity
        for file in uploaded_files:
            # Use a fresh copy of the file for each processing step
            file_copy = file.getvalue()
            
            with st.expander(f"**File:** `{file.name}`", expanded=True):
                # --- Step 1: Parse Header ---
                st.subheader("1. Header Parsing")
                parameter, animal_ids, data_start_line = processing.parse_clams_header(io.BytesIO(file_copy))
                
                if parameter and animal_ids and data_start_line != -1:
                    st.success(f"**Parameter:** {parameter} | **Animals Found:** {len(animal_ids)} | **Data Starts at Line:** {data_start_line}")
                else:
                    st.error("Header parsing failed. Cannot proceed with this file.")
                    continue # Skip to the next file

                # --- Step 2: Parse Data Section ---
                st.subheader("2. Data Parsing & Transformation")
                df_tidy = processing.parse_clams_data(io.BytesIO(file_copy), data_start_line, animal_ids)

                if df_tidy is not None and not df_tidy.empty:
                    st.success(f"Successfully parsed and transformed data! Found **{len(df_tidy)}** valid data points.")
                    st.write("Here is a preview of the tidy data:")
                    st.dataframe(df_tidy.head())
                    st.write(f"**DataFrame Dimensions:** {df_tidy.shape[0]} rows × {df_tidy.shape[1]} columns")
                else:
                    st.error("Failed to parse the data section of the file.")

if __name__ == "__main__":
    main()