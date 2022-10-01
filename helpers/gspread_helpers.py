import datetime
from typing import List, Any

import gspread


def spreadsheet_exists(gc: gspread.client.Client, sheet_name: str) -> bool:
    """Check if a spreadsheet exists

    Args:
        gc: A gspread Client
        sheet_name: The name of the sheet

    Returns:
        True if it exists, False otherwise
    """
    return sheet_name in [sh["name"] for sh in gc.list_spreadsheet_files()]


def worksheet_exists(sh: gspread.spreadsheet.Spreadsheet, worksheet_title: str) -> bool:
    """Check if a worksheet exists

    Args:
        sh: A gspread Spreadsheet
        worksheet_title: The title of the sheet

    Returns:
        True if it exists, False otherwise
    """
    return worksheet_title in [ws.title for ws in sh.worksheets()]


def create_spreadsheet_if_not_exists(gc: gspread.client.Client, sh_name: str,
                                     writers: List[str]) -> gspread.spreadsheet.Spreadsheet:
    """Create a spreadsheet if the name is not already occupied, otherwise return existing spreadsheet

    Args:
        gc: A gspread Client
        sh_name: Name of spreadsheet
        writers: A list of emails who will have writing permissions

    Returns:
        A spreadsheet with the requested name
    """
    # If the spreadsheet exists, return it
    if spreadsheet_exists(gc, sh_name):
        return gc.open(sh_name)

    # Create the spreadsheet and give all writers write permission
    sh = gc.create(sh_name)
    for writer in writers:
        sh.share(writer, perm_type="user", role="writer")
    ws = sh.get_worksheet(0)

    # Rename the first slide to Playground. This slide should be used by users to do adhoc analysis, readme's etc.
    ws.update_title("Playground")

    return sh


def create_worksheet_if_not_exists(sh: gspread.spreadsheet.Spreadsheet, ws_title: str,
                                   headers: List[str]) -> gspread.worksheet.Worksheet:
    """Create a worksheet if the title is not already occupied, otherwise return existing worksheet

    Args:
        sh: A gspread Spreadsheet
        ws_title: The title of the worksheet
        headers: A list of headers for the worksheet

    Returns:
        A worksheet with the requested title
    """
    # If the worksheet exists, return it
    if worksheet_exists(sh, ws_title):
        return sh.worksheet(ws_title)

    # Create the worksheet with the provided headers
    ws = sh.add_worksheet(ws_title, 1, len(headers))

    # Add headers
    ws.append_row(headers)

    return ws


def get_header(ws: gspread.worksheet.Worksheet) -> List[str]:
    """Gets the first row of the worksheet

    Args:
        ws: A gspread Worksheet

    Returns:
        A list of headers
    """
    return ws.get("1:1")[0]


def safe_append_row(ws: gspread.worksheet.Worksheet, row: List[Any]):
    """Appends rows to a worksheet if the number of elements in the row is equal to the number of headers

    Args:
        ws: A gspread Worksheet
        row: A list of elements to add to the sheet

    Raises:
        ValueError
    """
    # Validate that the number of elements in the row matches the header count
    headers = get_header(ws)
    if len(headers) != len(row):
        raise ValueError("Row can require more columns than already exists in the worksheet")

    # Append row as user input to allow for formatting by google sheets
    ws.append_row(row, value_input_option=gspread.worksheet.ValueInputOption.user_entered)
