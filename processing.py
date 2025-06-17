import streamlit as st
import pandas as pd
import io
import re

def parse_clams_header(uploaded_file):
    """
    Parses the header of a single CLAMS data file to extract metadata.
    """
    parameter = None
    animal_ids = {}
    data_start_line = -1
    current_cage_num_str = None

    uploaded_file.seek(0)
    lines = io.TextIOWrapper(uploaded_file, encoding='utf-8', errors='ignore').readlines()

    for i, line in enumerate(lines):
        clean_line = line.strip()
        if not clean_line: continue

        parts = [p.strip() for p in clean_line.split(',')]
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
                cage_key = f"CAGE {current_cage_num_str}"
                animal_ids[cage_key] = subject_id
                current_cage_num_str = None
        elif ":DATA" in line:
            header_line_index = next((idx for idx, l in enumerate(lines[i:], i) if "INTERVAL" in l and "," in l), -1)
            data_start_line = header_line_index
            break
            
    return parameter, animal_ids, data_start_line


def parse_clams_data(uploaded_file, data_start_line, animal_ids):
    """
    Parses the data section of a CLAMS file using modern Pandas, which handles
    duplicate column names by default.
    """
    if data_start_line == -1:
        st.error("Cannot parse data because the 'INTERVAL' header line was not found.")
        return None

    uploaded_file.seek(0)
    
    try:
        df_wide = pd.read_csv(
            uploaded_file,
            sep=',',
            skiprows=data_start_line
        )
        # Drop empty columns that can result from trailing commas
        df_wide = df_wide.loc[:, ~df_wide.columns.str.contains('^Unnamed')]
        
    except Exception as e:
        st.error(f"Error reading the data section with Pandas: {e}")
        return None

    all_animals_data = []
    cage_columns = [col for col in df_wide.columns if str(col).strip().upper().startswith('CAGE')]

    for i, cage_col_name in enumerate(cage_columns):
        time_col_name = 'TIME' if i == 0 else f'TIME.{i}'
        
        # Clean the cage column name just in case
        clean_cage_col = cage_col_name.strip()

        if time_col_name not in df_wide.columns:
            st.warning(f"Could not find a matching time column '{time_col_name}' for cage '{clean_cage_col}'. Skipping.")
            continue

        temp_df = df_wide[[time_col_name, clean_cage_col]].copy()
        temp_df.columns = ['timestamp_str', 'value']

        try:
            # Normalize key from header dict, e.g., 'CAGE 0101' -> 'CAGE 101'
            cage_num = int(re.findall(r'\d+', clean_cage_col)[0])
            animal_id_key = f"CAGE {cage_num}"
            subject_id = animal_ids.get(animal_id_key, clean_cage_col)
            temp_df['animal_id'] = subject_id
        except (IndexError, TypeError):
            temp_df['animal_id'] = clean_cage_col
            
        all_animals_data.append(temp_df)

    if not all_animals_data:
        st.error("Could not extract any animal data columns. Check if data columns are named 'CAGE...'.")
        return None

    df_tidy = pd.concat(all_animals_data, ignore_index=True)
    
    df_tidy.dropna(subset=['timestamp_str', 'value'], inplace=True)
    # Let pandas infer the datetime format (Bug Fix)
    df_tidy['timestamp'] = pd.to_datetime(df_tidy['timestamp_str'], errors='coerce')
    df_tidy['value'] = pd.to_numeric(df_tidy['value'], errors='coerce')
    df_tidy.dropna(subset=['timestamp', 'value'], inplace=True)

    if df_tidy.empty:
        st.error("Data is empty after type conversion. Check file for non-numeric values or incorrect date formats.")
        return None

    df_tidy = df_tidy[['animal_id', 'timestamp', 'value']]
    df_tidy.sort_values(by=['animal_id', 'timestamp'], inplace=True)

    return df_tidy.reset_index(drop=True)