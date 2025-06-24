# processing.py

import streamlit as st
import pandas as pd
import io
import re
from datetime import timedelta

def parse_clams_header(lines):
    """
    Parses the header of a CLAMS data file from a list of strings to extract metadata.
    This version is robust to both comma and tab delimiters in the header.
    
    Args:
        lines (list): The content of the file as a list of strings.
    """
    parameter = None
    animal_ids = {}
    data_start_line = -1
    current_cage_num_str = None

    for i, line in enumerate(lines):
        clean_line = line.strip()
        if not clean_line:
            continue

        # --- FIX: Robustly split header lines on the first delimiter found ---
        if ',' in clean_line:
            parts = [p.strip() for p in clean_line.split(',', 1)]
        elif '\t' in clean_line:
            parts = [p.strip() for p in clean_line.split('\t', 1)]
        else:
            parts = [clean_line]  # Handle lines with no delimiter

        first_part = parts[0].lower()

        if 'paramter' in first_part:
            if len(parts) > 1:
                name_part = parts[1]
                paren_pos = name_part.find('(')
                parameter = name_part[:paren_pos].strip() if paren_pos != -1 else name_part
        elif 'group/cage' in first_part:
            if len(parts) > 1:
                # Remove leading zeros before converting to int, handles '0101'
                current_cage_num_str = parts[1].lstrip('0')
        elif 'subject id' in first_part and current_cage_num_str is not None:
            if len(parts) > 1:
                subject_id = parts[1]
                # Pad with zeros to create the CAGE XXXX format for matching
                cage_key = f"CAGE {int(current_cage_num_str):04d}"
                animal_ids[cage_key] = subject_id
                current_cage_num_str = None
        elif ":DATA" in line:
            data_start_line = i # Line index where :DATA is found
            break

    return parameter, animal_ids, data_start_line


def parse_clams_data(lines, data_start_line, animal_ids):
    """
    Parses the data section of a CLAMS file from a list of strings into a tidy DataFrame.
    This version auto-detects the delimiter and handles multiple timestamp formats.
    
    Args:
        lines (list): The content of the file as a list of strings.
        data_start_line (int): The line number where the data starts.
        animal_ids (dict): A mapping from CAGE names to Subject IDs.
    """
    if data_start_line == -1:
        st.error("Cannot parse data because ':DATA' marker was not found.")
        return None

    try:
        header_line_index = -1
        header_line_str = ""
        # Find the actual header line by skipping blank lines and decorators after :DATA
        for i, line in enumerate(lines[data_start_line + 1:]):
            clean_line = line.strip()
            if clean_line and not clean_line.startswith('==='):
                header_line_index = data_start_line + 1 + i
                header_line_str = clean_line
                break
        
        if header_line_index == -1:
            st.error("Could not find the 'INTERVAL' data header row after the :DATA marker.")
            return None

        # --- FIX 1: DYNAMIC DELIMITER DETECTION ---
        separator = ',' if header_line_str.count(',') > header_line_str.count('\t') else '\t'

        # Join the relevant lines into a single string for pandas, starting from the true header
        data_as_string = "\n".join(lines[header_line_index:])
        
        df_wide = pd.read_csv(
            io.StringIO(data_as_string),
            sep=separator,
            on_bad_lines='skip',
            low_memory=False,
            # This is crucial for comma-separated files with spaces like the example
            skipinitialspace=True if separator == ',' else False 
        )

    except Exception as e:
        st.error(f"Error reading the data section with Pandas: {e}")
        return None

    # Clean column names by stripping whitespace
    df_wide.columns = [str(col).strip() for col in df_wide.columns]

    if 'INTERVAL' not in df_wide.columns:
        st.error(f"Parsing failed: 'INTERVAL' column not found. Detected separator as '{separator}'. Check file format.")
        return None
    
    df_wide['INTERVAL'] = pd.to_numeric(df_wide['INTERVAL'], errors='coerce')
    df_wide.dropna(subset=['INTERVAL'], inplace=True)

    all_animals_data = []
    cage_columns = [col for col in df_wide.columns if col.upper().startswith('CAGE')]
    
    for i, cage_col_name in enumerate(cage_columns):
        time_col_name = 'TIME' if i == 0 else f'TIME.{i}'
        
        if time_col_name in df_wide.columns and cage_col_name in df_wide.columns:
            temp_df = df_wide[[time_col_name, cage_col_name]].copy()
            temp_df.columns = ['timestamp', 'value']
            
            subject_id = animal_ids.get(cage_col_name, cage_col_name)
            temp_df['animal_id'] = subject_id
            all_animals_data.append(temp_df)

    if not all_animals_data:
        st.error("Could not extract any animal data columns. Check the file's data table format.")
        return None

    df_tidy = pd.concat(all_animals_data, ignore_index=True)
    df_tidy.dropna(subset=['timestamp', 'value'], inplace=True)
    
    # --- FIX 2: ROBUST TIMESTAMP PARSING ---
    # Let pandas infer the format automatically to handle both 24h and AM/PM
    df_tidy['timestamp'] = pd.to_datetime(df_tidy['timestamp'], errors='coerce')
    df_tidy['value'] = pd.to_numeric(df_tidy['value'], errors='coerce')
    
    df_tidy.dropna(subset=['timestamp', 'value'], inplace=True)
    
    # --- FIX 3: FILTER JUNK ROWS ---
    # Filter out the common zero-value artifact rows at the end of files.
    df_tidy = df_tidy[df_tidy['value'] != 0]

    df_tidy = df_tidy[['animal_id', 'timestamp', 'value']]
    df_tidy.sort_values(by=['animal_id', 'timestamp'], inplace=True)

    return df_tidy.reset_index(drop=True)


# --- NEW UTILITY FUNCTION ---
def parse_lean_mass_data(lean_mass_input):
    """
    Parses lean mass data from either an uploaded file object or a raw text string.
    Expected format is a two-column CSV-like structure: animal_id, lean_mass.
    Headers are not expected.

    Args:
        lean_mass_input: An uploaded file object (e.g., BytesIO) or a raw string from st.text_area.

    Returns:
        tuple: A tuple containing (lean_mass_map, error_message).
               - lean_mass_map (dict): A dictionary mapping animal_id (str) to lean_mass (float).
               - error_message (str or None): A string with an error if parsing fails, else None.
    """
    if not lean_mass_input:
        return {}, None

    try:
        if isinstance(lean_mass_input, str):
            source = io.StringIO(lean_mass_input)
        else: # Assumes it's a file-like object from st.file_uploader
            source = lean_mass_input

        df = pd.read_csv(
            source,
            header=None,
            names=['animal_id', 'lean_mass'],
            skipinitialspace=True,
            dtype={'animal_id': str} # Ensure animal IDs are read as strings
        )

        # Validate that lean_mass column is numeric
        df['lean_mass'] = pd.to_numeric(df['lean_mass'], errors='coerce')
        if df['lean_mass'].isnull().any():
            return None, "Error: The 'lean_mass' column contains non-numeric values. Please check your data."

        # Convert to dictionary
        lean_mass_map = df.set_index('animal_id')['lean_mass'].to_dict()
        # Clean keys by stripping any whitespace
        lean_mass_map = {str(k).strip(): float(v) for k, v in lean_mass_map.items()}
        return lean_mass_map, None

    except Exception as e:
        return None, f"An unexpected error occurred while parsing the lean mass data. Please ensure it is a two-column format (animal_id, mass). Details: {e}"


def filter_data_by_time(df, time_window_option, custom_start, custom_end):
    """Filters the dataframe based on the selected time window."""
    if not isinstance(df, pd.DataFrame) or 'timestamp' not in df.columns:
        return pd.DataFrame() # Return empty DataFrame if input is invalid
    
    df_copy = df.copy()

    if time_window_option == "Entire Dataset":
        return df_copy

    # Ensure timestamp is datetime before comparisons
    if not pd.api.types.is_datetime64_any_dtype(df_copy['timestamp']):
         df_copy['timestamp'] = pd.to_datetime(df_copy['timestamp'], errors='coerce')
         df_copy.dropna(subset=['timestamp'], inplace=True)

    duration_map = {
        "Last 24 Hours": timedelta(hours=24),
        "Last 48 Hours": timedelta(hours=48),
        "Last 72 Hours": timedelta(hours=72),
    }

    if time_window_option in duration_map:
        if df_copy.empty: return df_copy
        max_time = df_copy['timestamp'].max()
        cutoff_time = max_time - duration_map[time_window_option]
        return df_copy[df_copy['timestamp'] >= cutoff_time]
        
    elif time_window_option == "Custom...":
        if df_copy.empty or custom_start is None or custom_end is None: return df_copy
        min_time = df_copy['timestamp'].min()
        start_time = min_time + timedelta(hours=custom_start)
        end_time = min_time + timedelta(hours=custom_end)
        return df_copy[(df_copy['timestamp'] >= start_time) & (df_copy['timestamp'] <= end_time)]
        
    return df_copy

def add_light_dark_cycle_info(df, light_start, light_end):
    """Adds a 'period' column (Light/Dark) to the dataframe."""
    if not isinstance(df, pd.DataFrame) or 'timestamp' not in df.columns or df.empty:
        return df # Return original/empty df if invalid
        
    df_copy = df.copy()

    # Ensure timestamp is datetime before using .dt accessor
    if not pd.api.types.is_datetime64_any_dtype(df_copy['timestamp']):
         df_copy['timestamp'] = pd.to_datetime(df_copy['timestamp'], errors='coerce')
         df_copy.dropna(subset=['timestamp'], inplace=True)

    df_copy['hour'] = df_copy['timestamp'].dt.hour
    
    if light_start < light_end:
        # Standard day cycle (e.g., light starts at 7, ends at 19)
        df_copy['period'] = df_copy['hour'].apply(lambda h: 'Light' if light_start <= h < light_end else 'Dark')
    else:
        # Inverted cycle (e.g., light starts at 19, ends at 7)
        df_copy['period'] = df_copy['hour'].apply(lambda h: 'Dark' if light_end <= h < light_start else 'Light')
        
    df_copy = df_copy.drop(columns=['hour'])
    return df_copy


def add_group_info(df, group_assignments):
    """
    Adds a 'group' column to the dataframe based on user assignments.

    Args:
        df (pd.DataFrame): The data frame, must contain 'animal_id'.
        group_assignments (dict): A dictionary mapping group names to lists of animal IDs.

    Returns:
        pd.DataFrame: The dataframe with an added 'group' column.
    """
    if 'animal_id' not in df.columns:
        return df

    # Create a mapping from animal ID to group name for efficient lookup
    animal_to_group_map = {
        str(animal).strip(): group_name
        for group_name, animals in group_assignments.items()
        for animal in animals
    }

    df_copy = df.copy()
    # **FIX:** Use the `.str` accessor to apply the strip method to each element in the Series.
    df_copy['group'] = df_copy['animal_id'].astype(str).str.strip().map(animal_to_group_map).fillna('Unassigned')
    
    return df_copy

# --- NEW FUNCTION ---
def apply_normalization(df, mode, lean_mass_map):
    """
    Applies the selected normalization to the 'value' column of the dataframe.

    Args:
        df (pd.DataFrame): The data frame with 'animal_id' and 'value' columns.
        mode (str): The normalization mode ("Absolute Values", "Lean Mass Normalized", etc.).
        lean_mass_map (dict): A dictionary mapping animal_id to lean mass.

    Returns:
        pd.DataFrame: The dataframe with the 'value' column normalized.
    """
    df_copy = df.copy()

    if mode == "Absolute Values":
        # `[Sanity Check]` No action needed, return the original data.
        return df_copy
    
    if mode == "Body Weight Normalized":
        # `[Sanity Check]` This is a placeholder for a future feature.
        st.warning("Body Weight Normalization is not yet implemented. Showing absolute values.", icon="⚠️")
        return df_copy

    if mode == "Lean Mass Normalized":
        if not lean_mass_map:
            st.error("Lean Mass normalization selected, but no valid lean mass data was provided. Aborting.", icon="🚨")
            return pd.DataFrame() # Return empty DF to stop further processing

        df_copy['lean_mass'] = df_copy['animal_id'].map(lean_mass_map)

        # `[Sanity Check]` Verify which animals are missing from the lean mass map.
        missing_animals = df_copy[df_copy['lean_mass'].isnull()]['animal_id'].unique()
        if len(missing_animals) > 0:
            st.warning(f"Missing lean mass data for animals: `{', '.join(missing_animals)}`. They will be excluded from the analysis.", icon="⚠️")
        
        df_copy.dropna(subset=['lean_mass'], inplace=True)
        if df_copy.empty:
             st.error("No animals had corresponding lean mass data. Aborting analysis.", icon="🚨")
             return pd.DataFrame()

        # Apply the normalization
        df_copy['value'] = df_copy['value'] / df_copy['lean_mass']
        return df_copy
    
    return df_copy

def calculate_summary_stats_per_animal(df):
    """
    Calculates summary statistics (Light, Dark, Total averages) for each animal.
    This is for the main data table display.
    """
    # This function is the same as the old `calculate_summary_stats`
    if df.empty or 'value' not in df.columns or 'period' not in df.columns:
        return pd.DataFrame()

    total_avg = df.groupby(['animal_id', 'group'])['value'].mean().reset_index()
    total_avg.rename(columns={'value': 'Total_Average'}, inplace=True)

    period_avg = df.pivot_table(
        index=['animal_id', 'group'],
        columns='period',
        values='value',
        aggfunc='mean'
    ).reset_index()
    period_avg.columns.name = None

    summary_df = pd.merge(total_avg, period_avg, on=['animal_id', 'group'], how='left')

    if 'Light' not in summary_df.columns:
        summary_df['Light'] = pd.NA
    if 'Dark' not in summary_df.columns:
        summary_df['Dark'] = pd.NA
        
    summary_df.rename(columns={'Light': 'Light_Average', 'Dark': 'Dark_Average'}, inplace=True)
    
    final_cols = ['animal_id', 'group', 'Light_Average', 'Dark_Average', 'Total_Average']
    existing_cols = [col for col in final_cols if col in summary_df.columns]
    summary_df = summary_df[existing_cols]

    return summary_df.round(4)


# --- NEW FUNCTION ---
def calculate_summary_stats_per_group(df):
    """
    Calculates summary statistics (mean, sem, count) for each experimental GROUP.
    This is specifically for creating the summary bar chart.

    Args:
        df (pd.DataFrame): The processed dataframe with 'group', 'value', and 'period' columns.

    Returns:
        pd.DataFrame: A summary dataframe with one row per group/period combination.
    """
    if df.empty or 'group' not in df.columns or 'period' not in df.columns:
        return pd.DataFrame()

    # Use .agg() to calculate mean, standard error of mean (sem), and count (n)
    group_stats = df.groupby(['group', 'period'])['value'].agg(['mean', 'sem', 'count']).reset_index()
    
    # Sort for consistent plotting order
    group_stats.sort_values(by=['group', 'period'], inplace=True)
    
    return group_stats.round(4)