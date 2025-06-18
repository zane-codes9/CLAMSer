# processing.py

import streamlit as st
import pandas as pd
import io
import re
from datetime import timedelta

def parse_clams_header(uploaded_file):
    """
    Parses the header of a single CLAMS data file to extract metadata.
    This version correctly formats cage IDs to match data columns.
    """
    parameter = None
    animal_ids = {}
    data_start_line = -1
    current_cage_num_str = None

    uploaded_file.seek(0)
    lines = io.TextIOWrapper(uploaded_file, encoding='utf-8', errors='ignore').readlines()

    for i, line in enumerate(lines):
        clean_line = line.strip()
        if not clean_line:
            continue

        parts = [p.strip() for p in re.split(r'[,|\t]', clean_line, 1)] # Split only on the first delimiter
        first_part = parts[0].lower()

        if 'paramter' in first_part:
            if len(parts) > 1:
                name_part = parts[1]
                paren_pos = name_part.find('(')
                parameter = name_part[:paren_pos].strip() if paren_pos != -1 else name_part
        elif 'group/cage' in first_part:
            if len(parts) > 1:
                current_cage_num_str = parts[1]
        elif 'subject id' in first_part and current_cage_num_str is not None:
            if len(parts) > 1:
                subject_id = parts[1]
                # FIX: Format cage number with leading zeros to match data columns (e.g., CAGE 0101)
                cage_key = f"CAGE {int(current_cage_num_str):04d}"
                animal_ids[cage_key] = subject_id
                current_cage_num_str = None
        elif ":DATA" in line:
            data_start_line = i + 1
            break

    return parameter, animal_ids, data_start_line

def parse_clams_data(uploaded_file, data_start_line, animal_ids):
    """
    Parses the data section of a CLAMS file into a tidy DataFrame.
    This version is robust against premature file-closing errors.
    """
    if data_start_line == -1:
        st.error("Cannot parse data because ':DATA' marker was not found.")
        return None

    try:
        # --- FIX: Read the entire file into a list of strings ONCE ---
        uploaded_file.seek(0)
        lines = uploaded_file.read().decode('utf-8', errors='ignore').splitlines()

        # Find the header row's index number
        header_line_index = -1
        # Search only in the part of the file where the data should be
        for i, line in enumerate(lines[data_start_line:]):
            if line.strip().startswith('INTERVAL'):
                # The index is relative to the start of the data section, so add the offset
                header_line_index = data_start_line + i
                break
        
        if header_line_index == -1:
            st.error("Could not find the 'INTERVAL' data header row after the :DATA marker.")
            return None

        # --- FIX: Pass the relevant lines (as a single string) to Pandas ---
        # Re-join the lines from the header onwards into a single string
        data_as_string = "\n".join(lines[header_line_index:])
        
        # Use io.StringIO to treat the string as a file
        df_wide = pd.read_csv(
            io.StringIO(data_as_string),
            sep='\t',
            on_bad_lines='skip',
            low_memory=False
        )

    except Exception as e:
        st.error(f"Error reading the data section with Pandas: {e}")
        return None

    # This robustness check is still valuable.
    if 'INTERVAL' not in df_wide.columns:
        st.error("Parsing failed: 'INTERVAL' column not found. Check file delimiter.")
        return None
    df_wide['INTERVAL'] = pd.to_numeric(df_wide['INTERVAL'], errors='coerce')
    df_wide.dropna(subset=['INTERVAL'], inplace=True)

    all_animals_data = []
    
    df_wide.columns = df_wide.columns.str.strip()
    cage_columns = [col for col in df_wide.columns if col.upper().startswith('CAGE')]

    for i, cage_col_name in enumerate(cage_columns):
        time_col_name = f'TIME' if i == 0 else f'TIME.{i}'
        
        if time_col_name not in df_wide.columns:
            continue

        temp_df = df_wide[[time_col_name, cage_col_name]].copy()
        temp_df.columns = ['timestamp', 'value']
        
        subject_id = animal_ids.get(cage_col_name, cage_col_name)
        temp_df['animal_id'] = subject_id
        all_animals_data.append(temp_df)

    if not all_animals_data:
        st.error("Could not extract any animal data from the file.")
        return None

    df_tidy = pd.concat(all_animals_data, ignore_index=True)
    df_tidy.dropna(subset=['timestamp', 'value'], inplace=True)
    
    df_tidy['timestamp'] = pd.to_datetime(df_tidy['timestamp'], format='%d/%m/%Y %H:%M', errors='coerce')
    df_tidy['value'] = pd.to_numeric(df_tidy['value'], errors='coerce')
    
    df_tidy.dropna(subset=['timestamp', 'value'], inplace=True)
    
    df_tidy = df_tidy[['animal_id', 'timestamp', 'value']]
    df_tidy.sort_values(by=['animal_id', 'timestamp'], inplace=True)

    return df_tidy.reset_index(drop=True)