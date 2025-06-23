# plotting.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import time, timedelta

def create_timeline_chart(df, light_start, light_end, parameter_name):
    """
    Generates an interactive Plotly timeline chart.
    Assumes the input DataFrame `df` already contains the 'group' column.
    """
    if df.empty:
        fig = px.line(title=f"No data available for {parameter_name}")
        fig.update_layout(xaxis_title="Date and Time", yaxis_title=parameter_name)
        return fig

    # The 'group' column is now expected to be in the dataframe already.
    if 'group' not in df.columns:
        st.error("Plotting error: 'group' column not found in the dataframe.")
        df['group'] = 'Unassigned' # Fallback

    # Create the main line plot
    fig = px.line(
        df,
        x='timestamp',
        y='value',
        color='group',
        hover_name='animal_id',
        title=f"Timeline for {parameter_name}",
        labels={
            "timestamp": "Date and Time",
            "value": parameter_name,
            "group": "Group"
        }
    )
    fig.update_traces(line=dict(width=1.2))

    # Add shaded regions for the dark cycle
    min_date = df['timestamp'].min().date()
    max_date = df['timestamp'].max().date()
    current_date = min_date
    annotation_added = False

    while current_date <= max_date:
        vrect_args = {
            "fillcolor": "rgba(70, 70, 70, 0.2)",
            "layer": "below",
            "line_width": 0,
        }
        if not annotation_added:
            vrect_args["annotation_text"] = "Dark"
            vrect_args["annotation_position"] = "top left"
        
        if light_start < light_end: # Standard day cycle
            dark_start_time = pd.Timestamp.combine(current_date, time(hour=light_end))
            next_day_light_start_time = pd.Timestamp.combine(current_date + timedelta(days=1), time(hour=light_start))
            if dark_start_time < df['timestamp'].max() and next_day_light_start_time > df['timestamp'].min():
                fig.add_vrect(x0=dark_start_time, x1=next_day_light_start_time, **vrect_args)
                annotation_added = True
        else: # Inverted day cycle
            dark_start_1 = pd.Timestamp.combine(current_date, time(hour=0))
            dark_end_1 = pd.Timestamp.combine(current_date, time(hour=light_end))
            if dark_start_1 < df['timestamp'].max() and dark_end_1 > df['timestamp'].min():
                 fig.add_vrect(x0=dark_start_1, x1=dark_end_1, **vrect_args)
                 annotation_added = True
                 if "annotation_text" in vrect_args:
                     del vrect_args["annotation_text"]
            dark_start_2 = pd.Timestamp.combine(current_date, time(hour=light_start))
            dark_end_2 = pd.Timestamp.combine(current_date, time(hour=23, minute=59, second=59))
            if dark_start_2 < df['timestamp'].max() and dark_end_2 > df['timestamp'].min():
                fig.add_vrect(x0=dark_start_2, x1=dark_end_2, **vrect_args)
                annotation_added = True
        
        current_date += timedelta(days=1)
        if "annotation_text" in vrect_args:
            del vrect_args["annotation_text"]

    fig.update_layout(
        xaxis_title="Date and Time",
        yaxis_title=parameter_name,
        legend_title="Group"
    )

    return fig


# --- NEW FUNCTION ---
def create_summary_bar_chart(df, parameter_name):
    """
    Generates a grouped bar chart of Light vs. Dark averages for each group.
    Includes error bars for Standard Error of the Mean (SEM).

    Args:
        df (pd.DataFrame): The summary statistics dataframe per group, 
                           must contain 'group', 'period', 'mean', and 'sem'.
        parameter_name (str): The name of the parameter being plotted.

    Returns:
        A Plotly Figure object.
    """
    if df.empty or not all(col in df.columns for col in ['group', 'period', 'mean', 'sem']):
        fig = px.bar(title="Not enough data to generate summary bar chart.")
        return fig
        
    fig = px.bar(
        df,
        x='group',
        y='mean',
        color='period',
        barmode='group',
        error_y='sem',  # This adds the error bars
        title=f"Group Averages for {parameter_name}",
        labels={
            "group": "Experimental Group",
            "mean": f"Average {parameter_name}",
            "period": "Period"
        },
        color_discrete_map={ # Optional: Consistent coloring
            'Light': 'gold',
            'Dark': 'navy'
        }
    )
    
    fig.update_layout(
        xaxis_title="Experimental Group",
        yaxis_title=f"Average {parameter_name}",
        legend_title="Period"
    )
    
    return fig