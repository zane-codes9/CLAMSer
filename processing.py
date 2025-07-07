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
    """
    parameter = None
    animal_ids = {}
    data_start_line = -1
    current_cage_num_str = None

    for i, line in enumerate(lines):
        clean_line = line.strip()
        if not clean_line:
            continue
        
        # Stop parsing if we hit the data section marker
        if ":DATA" in line:
            data_start_line = i
            break

        if ',' in clean_line:
            parts = [p.strip() for p in clean_line.split(',', 1)]
        elif '\t' in clean_line:
            parts = [p.strip() for p in clean_line.split('\t', 1)]
        else:
            parts = [clean_line]

        first_part = parts[0].lower()

        if 'paramter' in first_part:
            if len(parts) > 1:
                name_part = parts[1]
                paren_pos = name_part.find('(')
                parameter = name_part[:paren_pos].strip() if paren_pos != -1 else name_part
        elif 'group/cage' in first_part:
            if len(parts) > 1:
                # This line is now safe from crashing the entire app
                current_cage_num_str = parts[1].lstrip('0')
        elif 'subject id' in first_part and current_cage_num_str is not None:
            if len(parts) > 1:
                subject_id = parts[1]
                # --- FIX 1: Add try-except block for robustness ---
                try:
                    cage_key = f"CAGE {int(current_cage_num_str):04d}"
                    animal_ids[cage_key] = subject_id
                except (ValueError, TypeError):
                    # This line is malformed, log it and skip this entry
                    print(f"Warning: Could not parse cage number '{current_cage_num_str}'. Skipping.")
                finally:
                    # Always reset to avoid carrying over a bad value
                    current_cage_num_str = None

    # If the :DATA marker was never found, this is not a data file.
    # Return silently; the calling function will handle skipping it.
    if data_start_line == -1:
        return None, None, -1

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

def parse_mass_data(mass_input, mass_type_name: str):
    """
    Parses mass data (body weight or lean mass) from an uploaded file or text.
    
    Args:
        mass_input: A file object or a raw text string.
        mass_type_name (str): The type of mass being parsed, for error messages.
    
    Returns:
        tuple: (mass_map, error_message)
    """
    if not mass_input:
        return {}, None

    try:
        source = io.StringIO(mass_input) if isinstance(mass_input, str) else mass_input
        df = pd.read_csv(
            source,
            header=None,
            names=['animal_id', 'mass'],
            skipinitialspace=True,
            dtype={'animal_id': str}
        )
        df['mass'] = pd.to_numeric(df['mass'], errors='coerce')
        if df['mass'].isnull().any():
            return None, f"The '{mass_type_name}' column contains non-numeric values. Please check your data."

        mass_map = df.set_index('animal_id')['mass'].to_dict()
        mass_map = {str(k).strip(): float(v) for k, v in mass_map.items()}
        return mass_map, None

    except Exception as e:
        return None, f"An unexpected error occurred parsing the {mass_type_name} data. Details: {e}"

def filter_data_by_time(df, time_window_option, custom_start, custom_end):
    """Filters the dataframe based on the selected time window."""
    if not isinstance(df, pd.DataFrame) or 'timestamp' not in df.columns:
        return pd.DataFrame() 
    
    df_copy = df.copy()

    if time_window_option == "Entire Dataset":
        return df_copy

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
        
    # --- START: REVISED LOGIC FOR CUSTOM TIME WINDOW ---
    elif time_window_option == "Custom...":
        if df_copy.empty or custom_start is None or custom_end is None: return df_copy
        
        # Filter based on the HOUR OF THE DAY, not hours from start
        hour_of_day = df_copy['timestamp'].dt.hour
        if custom_start <= custom_end:
            # Standard case (e.g., filter from hour 8 to 17)
            return df_copy[(hour_of_day >= custom_start) & (hour_of_day < custom_end)]
        else:
            # Inverted case (e.g., filter from hour 19 to 7 the next day)
            return df_copy[(hour_of_day >= custom_start) | (hour_of_day < custom_end)]
    # --- END: REVISED LOGIC ---
        
    return df_copy

def add_light_dark_cycle_info(df, light_start, light_end):
    """Adds a 'period' column (Light/Dark) to the dataframe."""
    if not isinstance(df, pd.DataFrame) or 'timestamp' not in df.columns or df.empty:
        return df # Return original/empty df if invalid

    df_copy = df.copy()

    if not pd.api.types.is_datetime64_any_dtype(df_copy['timestamp']):
         df_copy['timestamp'] = pd.to_datetime(df_copy['timestamp'], errors='coerce')
         df_copy.dropna(subset=['timestamp'], inplace=True)

    df_copy['hour'] = df_copy['timestamp'].dt.hour

    if light_start <= light_end:
        df_copy['period'] = df_copy['hour'].apply(lambda h: 'Light' if light_start <= h < light_end else 'Dark')
    else:
        df_copy['period'] = df_copy['hour'].apply(lambda h: 'Dark' if light_end <= h < light_start else 'Light')

    df_copy = df_copy.drop(columns=['hour'])
    return df_copy


def add_group_info(df, group_assignments):
    """
    Adds a 'group' column to the dataframe based on user assignments.
    """
    if 'animal_id' not in df.columns:
        return df

    animal_to_group_map = {
        str(animal).strip(): group_name
        for group_name, animals in group_assignments.items()
        for animal in animals
    }

    df_copy = df.copy()
    df_copy['group'] = df_copy['animal_id'].astype(str).str.strip().map(animal_to_group_map).fillna('Unassigned')
    return df_copy

# --- UPDATED FUNCTION ---
def apply_normalization(df, mode, body_weight_map, lean_mass_map):
    """
    Applies the selected normalization to the 'value' column of the dataframe.
    Now accepts both body weight and lean mass maps.
    """
    df_copy = df.copy()
    missing_animal_ids = []
    error_message = None

    if mode == "Absolute Values":
        return df_copy, missing_animal_ids, None

    elif mode == "Body Weight Normalized":
        if not body_weight_map:
            error_message = "Body Weight normalization selected, but no body weight data was provided. Displaying Absolute Values."
            return df_copy, list(df_copy['animal_id'].unique()), error_message
        
        df_copy['mass'] = df_copy['animal_id'].map(body_weight_map)
        mass_type = "body weight"

    elif mode == "Lean Mass Normalized":
        if not lean_mass_map:
            error_message = "Lean Mass normalization selected, but no lean mass data was provided. Displaying Absolute Values."
            return df_copy, list(df_copy['animal_id'].unique()), error_message
            
        df_copy['mass'] = df_copy['animal_id'].map(lean_mass_map)
        mass_type = "lean mass"
    else:
        return df_copy, [], "Invalid normalization mode selected."

    # Generic logic for both mass types
    missing_animals_mask = df_copy['mass'].isnull()
    missing_animal_ids = df_copy[missing_animals_mask]['animal_id'].unique().tolist()
    
    df_normalized = df_copy.dropna(subset=['mass']).copy()
    
    if df_normalized.empty:
         error_message = f"No animals in the current dataset had corresponding {mass_type} data."
         return pd.DataFrame(), missing_animal_ids, error_message

    df_normalized['value'] = df_normalized['value'] / df_normalized['mass']
    return df_normalized, missing_animal_ids, None


# --- NEW FUNCTION: OUTLIER FLAGGING ---
def flag_outliers(df, sd_threshold):
    """
    Flags outliers on a per-animal basis using the standard deviation method.
    
    Args:
        df (pd.DataFrame): Dataframe with 'animal_id' and 'value'.
        sd_threshold (float): The number of standard deviations to use as the cutoff.
                              If 0 or None, no flagging is performed.
    
    Returns:
        pd.DataFrame: The original dataframe with a new 'is_outlier' boolean column.
    """
    if sd_threshold is None or sd_threshold == 0:
        df['is_outlier'] = False
        return df

    df_copy = df.copy()
    # Use transform to calculate per-animal stats and broadcast them back to the original shape
    # This is much more efficient than a groupby().apply()
    animal_means = df_copy.groupby('animal_id')['value'].transform('mean')
    animal_stds = df_copy.groupby('animal_id')['value'].transform('std')
    
    # Calculate the Z-score for each data point relative to its own animal's stats
    # Fill NA for std (in case of single-point animals) to avoid division by zero
    z_scores = (df_copy['value'] - animal_means) / animal_stds.fillna(1)
    
    df_copy['is_outlier'] = z_scores.abs() > sd_threshold
    
    return df_copy


def calculate_summary_stats_per_animal(df):
    """
    Calculates summary statistics (Light, Dark, Total averages) for each animal.
    Now includes a count of outliers.
    """
    if df.empty or 'value' not in df.columns or 'period' not in df.columns:
        return pd.DataFrame()

    # --- CHANGE: ADD OUTLIER COUNT TO GROUPING ---
    agg_funcs = {
        'value': 'mean',
        'is_outlier': lambda x: x.sum() # Sum of True/False gives count of outliers
    }
    
    total_stats = df.groupby(['animal_id', 'group']).agg(agg_funcs).reset_index()
    total_stats.rename(columns={'value': 'Total_Average', 'is_outlier': 'Outlier_Count'}, inplace=True)
    total_stats['Outlier_Count'] = total_stats['Outlier_Count'].astype(int)

    period_avg = df.pivot_table(
        index=['animal_id', 'group'],
        columns='period',
        values='value',
        aggfunc='mean'
    ).reset_index()
    period_avg.columns.name = None

    summary_df = pd.merge(total_stats, period_avg, on=['animal_id', 'group'], how='left')

    if 'Light' not in summary_df.columns: summary_df['Light'] = pd.NA
    if 'Dark' not in summary_df.columns: summary_df['Dark'] = pd.NA
        
    summary_df.rename(columns={'Light': 'Light_Average', 'Dark': 'Dark_Average'}, inplace=True)
    
    # --- CHANGE: ADD OUTLIER COUNT TO FINAL COLS ---
    final_cols = ['animal_id', 'group', 'Light_Average', 'Dark_Average', 'Total_Average', 'Outlier_Count']
    existing_cols = [col for col in final_cols if col in summary_df.columns]
    
    return summary_df[existing_cols].round(4)


def calculate_summary_stats_per_group(df):
    """
    Calculates summary statistics (mean, sem, count) for each experimental GROUP.
    """
    if df.empty or 'group' not in df.columns or 'period' not in df.columns:
        return pd.DataFrame()

    group_stats = df.groupby(['group', 'period'])['value'].agg(['mean', 'sem', 'count']).reset_index()
    group_stats['sem'] = group_stats['sem'].fillna(0)
    group_stats.sort_values(by=['group', 'period'], inplace=True)
    
    return group_stats.round(4)


def calculate_key_metrics(df):
    """
    Calculates high-level metrics for the entire filtered dataset.
    """
    if df.empty or 'value' not in df.columns:
        return {
            'Overall Average': 'N/A',
            'Light Average': 'N/A',
            'Dark Average': 'N/A'
        }

    overall_avg = df['value'].mean()
    light_df = df[df['period'] == 'Light']
    dark_df = df[df['period'] == 'Dark']
    light_avg = light_df['value'].mean() if not light_df.empty else None
    dark_avg = dark_df['value'].mean() if not dark_df.empty else None

    metrics = {
        'Overall Average': f"{overall_avg:.2f}" if pd.notna(overall_avg) else 'N/A',
        'Light Average': f"{light_avg:.2f}" if pd.notna(light_avg) else 'N/A',
        'Dark Average': f"{dark_avg:.2f}" if pd.notna(dark_avg) else 'N/A'
    }
    
    return metrics

def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    """
    Converts a pandas DataFrame to a UTF-8 encoded CSV byte string.
    """
    return df.to_csv(index=False).encode('utf-8')

def calculate_interval_data(df):
    """
    Converts cumulative data to interval data by calculating the difference
    between consecutive measurements for each animal.
    """
    df_copy = df.copy()
    df_copy['value'] = df_copy.groupby('animal_id')['value'].diff()
    df_copy.dropna(subset=['value'], inplace=True)
    df_copy['value'] = df_copy['value'].clip(lower=0)
    return df_copy