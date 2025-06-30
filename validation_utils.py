# validation_utils.py

import pandas as pd


def generate_manual_validation_template(df: pd.DataFrame) -> bytes:
    """
    Takes a processed DataFrame and prepares it for manual validation.

    It selects and renames columns to be simple and clear for a user
    opening the file in Excel or Prism to create a pivot table.

    Args:
        df (pd.DataFrame): The dataframe after time filtering, light/dark
                           annotation, and group assignment. It should contain
                           'animal_id', 'group', 'period', and the 'value' column.

    Returns:
        bytes: A CSV file as a UTF-8 encoded byte string.
    """
    if df.empty or not all(
        col in df.columns for col in ["animal_id", "group", "period", "value"]
    ):
        # Create an empty but correctly formatted dataframe if input is bad
        validation_df = pd.DataFrame(columns=["Animal_ID", "Group", "Period", "Value"])
    else:
        validation_df = df[["animal_id", "group", "period", "value"]].copy()

    validation_df.rename(
        columns={
            "animal_id": "Animal_ID",
            "group": "Group",
            "period": "Period",
            "value": "Value",
        },
        inplace=True,
    )

    # Using the existing conversion utility to keep things consistent
    # We assume a function `convert_df_to_csv` exists in processing.
    # To avoid circular imports, let's duplicate this small function here.
    return validation_df.to_csv(index=False).encode("utf-8")
