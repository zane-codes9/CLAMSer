import streamlit as st
import pandas as pd
import io
import re

def parse_clams_header(uploaded_file):
    """
    Parses the header of a single CLAMS data file.

    Args:
        uploaded_file: A Streamlit UploadedFile object.

    Returns:
        A tuple containing:
        - parameter (str): The metabolic parameter identified (e.g., 'VO2').
        - animal_ids (dict): A mapping of cage numbers to subject IDs.
        - data_start_line (int): The line number where the data section begins.
    """
    parameter = None
    animal_ids = {}
    data_start_line = -1

    # Ensure we're at the start of the file
    uploaded_file.seek(0)
    # Use TextIOWrapper to read the file as text
    text_stream = io.TextIOWrapper(uploaded_file, encoding='utf-8')

    # Read all lines to avoid re-reading the stream
    lines = text_stream.readlines()

    for i, line in enumerate(lines):
        # 1. Identify the parameter
        if "PARAMETER File" in line:
            # Extract the parameter name, which is usually the first word
            match = re.search(r"(\w+)\s+PARAMETER File", line)
            if match:
                parameter = match.group(1)

        # 2. Identify animal IDs
        if "Subject ID" in line and (i + 1) < len(lines):
            # The next line contains the actual IDs, comma-separated
            id_line = lines[i + 1]
            ids = [id.strip() for id in id_line.strip().split(',')]
            # The CLAMS format is CAGE 01, CAGE 02, etc.
            for cage_num, animal_id in enumerate(ids, start=1):
                cage_key = f"CAGE {cage_num:02d}"
                animal_ids[cage_key] = animal_id

        # 3. Find the start of the data section
        if ":DATA" in line:
            data_start_line = i + 1
            break  # Stop parsing after :DATA is found

    return parameter, animal_ids, data_start_line