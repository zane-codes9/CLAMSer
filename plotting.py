# plotting.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import time, timedelta

def create_timeline_chart(df, light_start, light_end, parameter_name):
    """
    Generates an interactive Plotly timeline chart.
    Draws a continuous line PER ANIMAL, then overlays markers for outliers.
    """
    
    if df.empty:
        fig = px.line(title=f"No data available for {parameter_name}")
        fig.update_layout(xaxis_title="Date and Time", yaxis_title=parameter_name)
        return fig

    for col in ['group', 'animal_id', 'is_outlier']:
        if col not in df.columns:
            df[col] = 'Unassigned' if col != 'is_outlier' else False
    
    df = df.sort_values(by=['animal_id', 'timestamp'])

    fig = px.line(
        df,
        x='timestamp',
        y='value',
        color='group',
        line_group='animal_id',
        title=f"Timeline for {parameter_name}",
        labels={"timestamp": "Date and Time", "value": parameter_name, "group": "Group"},
        hover_data={'animal_id': True, 'timestamp': '|%Y-%m-%d %H:%M', 'value': ':.2f'}
    )
    
    fig.update_traces(line=dict(width=1.5))

    df_outliers = df[df['is_outlier']]
    
    if not df_outliers.empty:
        fig.add_trace(go.Scatter(
            x=df_outliers['timestamp'],
            y=df_outliers['value'],
            mode='markers',
            marker=dict(
                symbol='x',
                color='red',
                size=8,
                line=dict(width=1.5)
            ),
            name='Outlier',
            hoverinfo='text',
            text=[
                f"Animal: {row.animal_id}<br>Group: {row.group}<br>Value: {row.value:.2f}<br><b>(Outlier)</b>"
                for index, row in df_outliers.iterrows()
            ]
        ))

    min_date = df['timestamp'].min().date()
    max_date = df['timestamp'].max().date()
    current_date = min_date
    while current_date <= max_date + timedelta(days=1):
        if light_start < light_end:
             dark_start = pd.Timestamp.combine(current_date, time(hour=light_end))
             dark_end = pd.Timestamp.combine(current_date + timedelta(days=1), time(hour=light_start))
             if dark_start < df['timestamp'].max() and dark_end > df['timestamp'].min():
                fig.add_vrect(x0=dark_start, x1=dark_end, fillcolor="rgba(70, 70, 70, 0.2)", layer="below", line_width=0)
        else:
            dark_start1 = pd.Timestamp.combine(current_date, time(hour=0))
            dark_end1 = pd.Timestamp.combine(current_date, time(hour=light_end))
            if dark_start1 < df['timestamp'].max() and dark_end1 > df['timestamp'].min():
                fig.add_vrect(x0=dark_start1, x1=dark_end1, fillcolor="rgba(70, 70, 70, 0.2)", layer="below", line_width=0)
            
            dark_start2 = pd.Timestamp.combine(current_date, time(hour=light_start))
            dark_end2 = pd.Timestamp.combine(current_date, time(hour=23, minute=59, second=59))
            if dark_start2 < df['timestamp'].max() and dark_end2 > df['timestamp'].min():
                fig.add_vrect(x0=dark_start2, x1=dark_end2, fillcolor="rgba(70, 70, 70, 0.2)", layer="below", line_width=0)
        
        current_date += timedelta(days=1)

    fig.update_layout(xaxis_title="Date and Time", yaxis_title=parameter_name, legend_title="Group")
    return fig


def create_summary_bar_chart(df, parameter_name):
    """
    Generates a grouped bar chart of Light vs. Dark averages for each group.
    """
    if df.empty or not all(col in df.columns for col in ['group', 'period', 'mean', 'sem']):
        fig = px.bar(title="Not enough data to generate summary bar chart.")
        return fig
        
    fig = px.bar(
        df, x='group', y='mean', color='period', barmode='group',
        error_y='sem', title=f"Group Averages for {parameter_name}",
        labels={"group": "Experimental Group", "mean": f"Average {parameter_name}", "period": "Period"},
        color_discrete_map={'Light': 'gold', 'Dark': 'navy'}
    )
    fig.update_layout(xaxis_title="Experimental Group", yaxis_title=f"Average {parameter_name}", legend_title="Period")
    return fig