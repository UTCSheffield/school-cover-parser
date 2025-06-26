from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime
from pathlib import Path
import webbrowser
import win32com.client as client
import os

# PARAMETERS
do_email = False
# PARAMETERS END

# CONSTANTS
data_filename = "Notice Board Summary.html"
outputs_folder = "outputs"
templates_folder = "templates"
periods = {
    "MM": { "time": "08:30-08:45", "label": "MM" },
    "1": { "time": "08:45-09:40", "label": "1" },
    "2": { "time": "09:40-10:30", "label": "2" },
    "Tut": { "time": "10:30-10:45", "label": "Tutor A"},
    "Tut [1]": { "time": "10:45-11:00", "label": "Tutor B"},
    "Tut [1] [2]": { "time": "11:00-11:15", "label": "Tutor C"},
    "3": { "time": "11:15-12:10", "label": "3"},
    "4a": { "time": "12:10-12:40", "label": "4a"},
    "4":{ "time": "12:40-13:10", "label": "4b"},
    "4c": { "time": "13:10-13:40", "label": "4c"},
    "5": { "time": "13:40-14:35", "label": "5" },
    "6": { "time": "14:35-15:30", "label": "6" },
}
classroom_pattern = r"([A-Za-z]{2}[1-9]{1,2})|SOC|CQ|HS[LD]B|TLV"
staff_pattern = r"[A-Za-z]+, [A-Za-z ]+"
columns = [
    "Period", "Staff or Room to replace", "Reason", "Activity",
    "Rooms", "Staff", "Assigned Staff or Room", "Times"
]
# CONSTANTS END

# LOAD DATA
data_file_path = Path.joinpath(Path.home(), "Downloads", data_filename)
if Path(data_file_path).is_file():
    os.remove(data_file_path)

if not Path(data_file_path).is_file():
    data_file_path = Path.joinpath(Path.cwd(), "test_data", data_filename)
    if not Path(data_file_path).is_file():
        raise ValueError("Data file not found. Please ensure the HTML file is in the Downloads folder or in test_data folder.")

with open(data_file_path, "r", encoding="utf-8") as file:
    soup = BeautifulSoup(file, "html.parser")

rows = soup.find_all("tr")
data = []
for row in rows:
    cols = row.find_all("td")
    if not cols:
        continue
    values = [col.get_text(strip=True) for col in cols]
    if all(val == '' for val in values):
        continue
    data.append(values)
# LOAD DATA END

# DATE EXTRACTION
date_text = ""
for string in soup.stripped_strings:
    if "Full List of Staff and Room Details:" in string:
        match = re.search(r"Full List of Staff and Room Details:\s*(\d{1,2}-[A-Za-z]{3}-\d{4})", string)
        if match:
            date_text = match.group(1)
            break

formatted_date = "Unknown Date"

if date_text:
    try:
        date_obj = datetime.strptime(date_text, "%d-%b-%Y")
        formatted_date = date_obj.strftime("%A %d %B %Y")
    except ValueError:
        formatted_date = date_text
# DATE EXTRACTION END

# DATAFRAME + CLEANUP
cover_sheet = pd.DataFrame(data, columns=columns)

cover_sheet = cover_sheet.dropna(subset=["Staff or Room to replace", "Assigned Staff or Room"])
cover_sheet.drop(columns=["Reason"], inplace=True)
cover_sheet = cover_sheet[~cover_sheet["Assigned Staff or Room"].str.contains("No Cover Required", na=False)]
cover_sheet = cover_sheet[~cover_sheet["Period"].str.contains(":Enr|Mon:6|Fri:6")]
cover_sheet = cover_sheet[~cover_sheet["Activity"].str.contains("-")]

cover_sheet["Rooms"] = cover_sheet["Rooms"].str.replace(r"[()]", "", regex=True)
cover_sheet["Staff or Room to replace"] = cover_sheet["Staff or Room to replace"].str.replace(r"[()]", "", regex=True)
# DATAFRAME + CLEANUP END


def get_time(row):
    return periods.get(row['Period'])['time']

def label_period(row):
    return periods[row['Period']]['label']# if 'label' in periods[row['Period']] else row['Period']


# Extract year group for proper sorting (from Activity, assumed to be class names like '10A')
def extract_year(group):
    match = re.match(r"(\d+)", group)
    return int(match.group(1)) if match else 0


def normalize_rooms(val):
    if not isinstance(val, str) or val.strip() == "":
        return ""

    parts = val.split(";")
    if len(parts) == 1:
        return parts[0]  # just return the single remap or room

    first = parts[0]  # CL4>LB14
    # Extract all target rooms from remaps
    targets = [re.search(classroom_pattern, p) for p in parts[1:]]
    targets = [m.group(1) for m in targets if m]
    return f"{first}, {', '.join(targets)}" if targets else first

cover_sheet["Rooms"] = cover_sheet["Rooms"].apply(normalize_rooms)

# Extract assigned staff and room
cover_sheet.insert(
    cover_sheet.columns.get_loc("Assigned Staff or Room"),
    "Assigned Staff",
    cover_sheet["Assigned Staff or Room"].str.extract(r"([A-Za-z]+, [A-Za-z ]+)")[0]
)

# Match supply teachers and real teachers
assigned_staff = cover_sheet["Assigned Staff or Room"].str.extract(r"([A-Za-z]+, [A-Za-z ]+)")
supply_staff = cover_sheet["Assigned Staff or Room"].str.extract(r"(Supply \d)")
cover_sheet["Assigned Staff"] = assigned_staff[0].combine_first(supply_staff[0]).fillna("")
cover_sheet.insert(
    cover_sheet.columns.get_loc("Assigned Staff or Room"),
    "Assigned Room",
    cover_sheet["Rooms"].str.split(">", expand=True)[1]
)

# Extract Rooms
assigned_room = cover_sheet["Rooms"].str.split(">", expand=True)
cover_sheet["Assigned Room"] = assigned_room[1].replace("", pd.NA)
cover_sheet["Assigned Room"] = cover_sheet["Assigned Room"].fillna(assigned_room[0])
cover_sheet["Assigned Room"] = cover_sheet["Assigned Room"].replace("", pd.NA)
cover_sheet["Assigned Room"] = cover_sheet["Assigned Room"].fillna(cover_sheet["Assigned Staff or Room"].str.replace(staff_pattern, "", regex=True))

# Separate rows into staff and room based on pattern
is_staff = cover_sheet["Staff or Room to replace"].str.contains(staff_pattern)
is_room = cover_sheet["Staff or Room to replace"].str.match(classroom_pattern)

# Create separate DataFrames
staff_df = cover_sheet[is_staff].copy()
staff_df["Replaced Staff"] = staff_df["Staff or Room to replace"]
staff_df.drop(columns=["Staff or Room to replace"], inplace=True)

room_df = cover_sheet[is_room].copy()
room_df["Replaced Room"] = room_df["Staff or Room to replace"]
room_df.drop(columns=["Staff or Room to replace"], inplace=True)

merged_df = pd.merge(
    staff_df,
    room_df,
    on=["Activity", "Period"],
    how="outer",
    suffixes=("_staff", "_room")
)

for col in ["Assigned Staff", "Assigned Room", "Times"]:
    merged_df[col] = merged_df[col + "_staff"].combine_first(merged_df[col + "_room"])
    merged_df.drop(columns=[col + "_staff", col + "_room"], inplace=True)

merged_df = merged_df[[
    "Period", "Activity", "Replaced Staff", "Replaced Room",
    "Assigned Staff", "Assigned Room", "Times"
]]

merged_df.drop_duplicates(inplace=True)

#Simplified DataFrame start

simplified_sheet = merged_df
simplified_sheet = simplified_sheet.fillna("")

simplified_sheet.insert(
    0,
    "Day",
    simplified_sheet["Period"].str.split(":", expand=True)[0]
)
simplified_sheet["Period"] = simplified_sheet["Period"].str.split(":", expand=True)[1]
simplified_sheet['Time'] = simplified_sheet.apply(get_time, axis=1)
simplified_sheet['Period'] = simplified_sheet.apply(label_period, axis=1)
simplified_sheet["SortKey"] = simplified_sheet["Activity"].apply(extract_year)
simplified_sheet.sort_values(by=["Time", "SortKey", "Activity"], inplace=True)
simplified_sheet.drop(columns=["SortKey"], inplace=True)




if simplified_sheet['Times'].dropna().eq("").all():
    # All empty or blank
    html_table = simplified_sheet.to_html(
        index=False,
        escape=False,
        classes="cover-table",
        columns=["Period", "Activity", "Replaced Staff", "Replaced Room", "Assigned Staff", "Assigned Room"]
    )
else:
    html_table = simplified_sheet.to_html(
        index=False,
        escape=False,
        classes="cover-table",
        columns=["Period", "Activity", "Replaced Staff", "Replaced Room", "Assigned Staff", "Assigned Room", "Times"]
    )


# Replace <thead> in the original table with our big header + the original header
html_table = html_table.replace(
    "<thead>",
    big_header + "<thead>"
)

with open(Path.joinpath(Path.cwd(),templates_folder, "table_template.html"), "r", encoding="utf-8") as template:
    templateHtml = template.read()
    html_output = templateHtml.replace("{html_table}", html_table)

    cover_output_path = Path.joinpath(Path.cwd(), outputs_folder, "simplified_sheet.html")
    with open(cover_output_path, "w", encoding="utf-8") as f:
        f.write(html_output)
    
    if do_email:
        outlook = client.Dispatch('Outlook.Application')
        message = outlook.CreateItem(0)
        message.Subject = 'Cover & Room Change Summary - '+ formatted_date
        message.To = "allutcolpstaff@utcsheffield.org.uk"
        message.HTMLBody = html_output
        
        message.Display()
    else : 
        webbrowser.open(cover_output_path)

# Only keep rows where Assigned Staff is like "Supply 1", "Supply 2", etc.
supply_rows = simplified_sheet[simplified_sheet["Assigned Staff"].str.match(r"Supply \d+", na=False)].rename(columns={"Replaced Staff": "Teacher to Cover", "Assigned Room": "Room"}, inplace=False)
room_rows = simplified_sheet[simplified_sheet["Replaced Room"].str.match(classroom_pattern, na=False)]

# Get unique supply teachers, e.g. ["Supply 1", "Supply 2"]
unique_supply_staff = sorted(supply_rows["Assigned Staff"].unique())
unique_room_changes = sorted(room_rows["Replaced Room"].unique())
supply_room_tables = []
for supply in unique_supply_staff:
    filtered = supply_rows[supply_rows["Assigned Staff"] == supply].copy()

    # Get periods that are already assigned for this supply
    assigned_periods = set(filtered["Period"])

    # Fill in missing periods
    missing = [p for p in periods.values() if p['label'] not in assigned_periods]

    for p in missing:
        time = p["time"]
        label = p["label"]
        filtered = pd.concat([
            filtered,
            pd.DataFrame([{
                "Day": "",
                "Period": label,
                "Activity": "",
                "Teacher to Cover": "",
                "Room": "",
                "Time": time
            }])
        ], ignore_index=True)

    filtered["IsFree"] = filtered.get("IsFree", False)


    # Sort to keep order
    filtered["SortKey"] = filtered["Time"]
    filtered.sort_values(by="SortKey", inplace=True)
    filtered.drop(columns=["SortKey"], inplace=True)


    if filtered.empty:
        continue

    table_html = filtered.to_html(
        index=False,
        escape=False,
        classes=["cover-table", "supply-table"],
        columns=["Period", "Activity", "Teacher to Cover", "Room", "Time"],
    )

    num_cols = len(filtered.columns)

    # Create the header row
    big_header = f"""
    <thead>
        <tr>
            <th colspan="{num_cols}" style="text-align:center; font-size:24px; padding:10px;">
                {supply} Cover Assignments – {formatted_date}
            </th>
        </tr>
    </thead>
    """

    # Replace <thead> in the original table with our big header + the original header
    table_html = table_html.replace(
        "<thead>",
        big_header + "<thead>"
    )

    # Add section header + table
    supply_room_tables.append(table_html)
    
for room in unique_room_changes:
    filtered = simplified_sheet[simplified_sheet["Replaced Room"] == room].copy()

    # Get periods that are already assigned for this supply
    assigned_periods = set(filtered["Period"])

    # Fill in missing periods
    missing = [p for p in periods.values() if p['label'] not in assigned_periods]

    for p in missing:
        time = p["time"]
        label = p["label"]
        filtered = pd.concat([
            filtered,
            pd.DataFrame([{
                "Day": "",
                "Period": label,
                "Activity": "",
                "Replaced Room": "",
                "Assigned Room": "",
                "Time": time
            }])
        ], ignore_index=True)

    # Sort to keep order
    filtered["SortKey"] = filtered["Time"]
    filtered.sort_values(by="SortKey", inplace=True)
    filtered.drop(columns=["SortKey"], inplace=True)


    if filtered.empty:
        continue

    table_html = filtered.to_html(
        index=False,
        escape=False,
        classes=["cover-table", "room-table"],
        columns=["Period", "Activity", "Assigned Room"],
    )

    num_cols = len(filtered.columns)

    # Create the header row
    big_header = f"""
    <thead>
        <tr>
            <th colspan="{num_cols}" style="text-align:center; font-size:24px; padding:10px;">
                Room Changes for {room} – {formatted_date}
            </th>
        </tr>
    </thead>
    """

    # Replace <thead> in the original table with our big header + the original header
    table_html = table_html.replace(
        "<thead>",
        big_header + "<thead>"
    )

    # Add section header + table
    supply_room_tables.append(table_html)

supply_html = "<br><br>".join(supply_room_tables)

# For example, inject into a placeholder in template
with open( Path.joinpath(Path.cwd(),templates_folder, "table_template.html"), "r", encoding="utf-8") as template:
    template_html = template.read()

output_html = template_html.replace("{html_table}", supply_html)

supply_output_path = Path.joinpath(Path.cwd(), outputs_folder, "supply_tables.html")
with open(supply_output_path, "w", encoding="utf-8") as f:
    f.write(output_html)

webbrowser.open(supply_output_path)


