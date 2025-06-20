from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime

# Load the HTML content
with open("Notice Board Summary.html", "r", encoding="utf-8") as file:
    soup = BeautifulSoup(file, "html.parser")

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
        formatted_date = date_text  # fallback if format is weird

classroom_pattern = r"([A-Za-z]{2}[1-9]{1,2})|SOC|CQ|HSLB"

periods = {
    "MM": { "time": "08:30-08:45" },
    "1": { "time": "08:45-09:40" },
    "2": { "time": "09:40-10:30" },
    "Tut": { "time": "10:30-10:45", "label": "Tutor A"},
    "Tut [1]": { "time": "10:45-11:00", "label": "Tutor B"},
    "Tut [1] [2]": { "time": "11:00-11:15", "label": "Tutor C"},
    "3": { "time": "11:15-12:10", "label": "3"},
    "4a": { "time": "12:10-12:40", "label": "4a"},
    "4":{ "time": "12:40-13:10", "label": "4b"},
    "4c": { "time": "13:10-13:40", "label": "4c"},
    "5": { "time": "13:40-14:35" },
    "6": { "time": "14:35-15:30" },
}

# Extract table rows
rows = soup.find_all("tr")
data = []

# Extract and clean table data
for row in rows:
    cols = row.find_all("td")
    if not cols:
        continue
    values = [col.get_text(strip=True) for col in cols]
    if all(val == '' for val in values):
        continue
    data.append(values)

# Define column headers manually
columns = [
    "Period", "Staff or Room to replace", "Reason", "Activity",
    "Rooms", "Staff", "Assigned Staff or Room", "Times"
]

# Create DataFrame
cover_sheet = pd.DataFrame(data, columns=columns)

# Filter and clean blank and unimportant data
cover_sheet = cover_sheet.dropna(subset=["Staff or Room to replace", "Assigned Staff or Room"])
cover_sheet.drop(columns=["Reason"], inplace=True)
cover_sheet = cover_sheet[~cover_sheet["Assigned Staff or Room"].str.contains("No Cover Required", na=False)]
cover_sheet = cover_sheet[~cover_sheet["Period"].str.contains(":Enr|Mon:6|Fri:6")]
cover_sheet = cover_sheet[~cover_sheet["Activity"].str.contains("-")]

# Filter valid staff/room replacements
cover_sheet["Rooms"] = cover_sheet["Rooms"].str.replace(r"[()]", "", regex=True)
#pattern = r"(\([A-Za-z]{2}[1-9]{1,2}\))|([A-Za-z]{2}[1-9]{1,2})|(SOC)|(HSLB)|(CQ)|(Supply \d+)|([A-Za-z]+, [A-Za-z ]+)"
#cover_sheet = cover_sheet[cover_sheet["Staff or Room to replace"].str.match(pattern, na=False)]
cover_sheet["Staff or Room to replace"] = cover_sheet["Staff or Room to replace"].str.replace(r"[()]", "", regex=True)

def normalize_rooms(val):
    if not isinstance(val, str) or val.strip() == "":
        return ""

    parts = val.split(";")
    if len(parts) == 1:
        return parts[0]  # just return the single remap or room

    first = parts[0]  # CL4>LB14
    # Extract all target rooms from remaps
    targets = [re.search(r'>([A-Za-z]{2}[0-9]{1,2}|SOC|HSLB|HSDB|CQ|TLV)$', p) for p in parts[1:]]
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
cover_sheet["Assigned Room"] = cover_sheet["Assigned Room"].fillna(cover_sheet["Assigned Staff or Room"].str.split(">", expand=True)[0].replace(r"[A-Za-z]+, [A-Za-z ]+", "", regex=True))

# Display the last 20 rows
#print(cover_sheet.tail(20))

# Separate rows into staff and room based on pattern
is_staff = cover_sheet["Staff or Room to replace"].str.contains(r"[A-Za-z]+, [A-Za-z ]+")
is_room = cover_sheet["Staff or Room to replace"].str.match(classroom_pattern)

# Create separate DataFrames
staff_df = cover_sheet[is_staff].copy()
staff_df["Replaced Staff"] = staff_df["Staff or Room to replace"]
staff_df.drop(columns=["Staff or Room to replace"], inplace=True)

room_df = cover_sheet[is_room].copy()
room_df["Replaced Room"] = room_df["Staff or Room to replace"]
room_df.drop(columns=["Staff or Room to replace"], inplace=True)


# Merge on 'Activity' and 'Period' to keep context (more specific than just Activity)
merged_df = pd.merge(
    staff_df,
    room_df,
    on=["Activity", "Period"],
    how="outer",
    suffixes=("_staff", "_room")
)

# Combine fields that may be split across suffixes (since some rows are only in staff_df or room_df)
for col in ["Assigned Staff", "Assigned Room", "Times"]:
    merged_df[col] = merged_df[col + "_staff"].combine_first(merged_df[col + "_room"])
    merged_df.drop(columns=[col + "_staff", col + "_room"], inplace=True)

# Reorder columns if needed
merged_df = merged_df[[
    "Period", "Activity", "Replaced Staff", "Replaced Room",
    "Assigned Staff", "Assigned Room", "Times"
]]

merged_df.drop_duplicates(inplace=True)

simplified_sheet = merged_df
simplified_sheet = simplified_sheet.fillna("")

simplified_sheet.insert(
    0,
    "Day",
    simplified_sheet["Period"].str.split(":", expand=True)[0]
)
simplified_sheet["Period"] = simplified_sheet["Period"].str.split(":", expand=True)[1]

def get_time(row):
    return periods.get(row['Period'])['time']

simplified_sheet['Time'] = simplified_sheet.apply(get_time, axis=1)

def label_period(row):
    return periods[row['Period']]['label'] if 'label' in periods[row['Period']] else row['Period']
    
simplified_sheet['Period'] = simplified_sheet.apply(label_period, axis=1)

# Extract year group for proper sorting (from Activity, assumed to be class names like '10A')
def extract_year(group):
    match = re.match(r"(\d+)", group)
    return int(match.group(1)) if match else 0

simplified_sheet["SortKey"] = simplified_sheet["Activity"].apply(extract_year)

# Sort by Time (chronologically), then by Year group, then by Activity (e.g., A, B...)
simplified_sheet.sort_values(by=["Time", "SortKey", "Activity"], inplace=True)

# Drop the temporary column
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

# Count number of columns in the table
num_cols = len(simplified_sheet.columns)

# Create the header row
big_header = f"""
<thead>
    <tr>
        <th colspan="{num_cols}" style="text-align:center; font-size:24px; padding:10px; background-color:#f0f0f0;">
            Cover Summary – {formatted_date}
        </th>
    </tr>
</thead>
"""

# Replace <thead> in the original table with our big header + the original header
html_table = html_table.replace(
    "<thead>",
    big_header + "<thead>"
)

with open("table_template.html", "r", encoding="utf-8") as template:
    templateHtml = template.read()
    html_output = templateHtml.replace("{html_table}", html_table)
    with open("simplified_sheet.html", "w", encoding="utf-8") as f:
        f.write(html_output)

# Only keep rows where Assigned Staff is like "Supply 1", "Supply 2", etc.
supply_rows = simplified_sheet[simplified_sheet["Assigned Staff"].str.match(r"Supply \d+", na=False)]

# Get unique supply teachers, e.g. ["Supply 1", "Supply 2"]
unique_supply_staff = sorted(supply_rows["Assigned Staff"].unique())
supply_tables = ""


simplified_sheet.rename(columns={"Replaced Staff": "Teacher to Cover"}, inplace=True)
for supply in unique_supply_staff:
    filtered = simplified_sheet[simplified_sheet["Assigned Staff"] == supply]

    if filtered.empty:
        continue

    # Optional: Customize columns shown
    table_html = filtered.to_html(
        index=False,
        escape=False,
        classes="cover-table",
        columns=["Day", "Period", "Activity", "Teacher to Cover", "Assigned Room", "Time"]
    )

    # Add section header + table
    supply_tables += f"""
    <h2 style="font-family:sans-serif; color:#333;">{supply} Cover Assignments</h2>
    {table_html}
    <br><br>
    """

# For example, inject into a placeholder in template
with open("table_template.html", "r", encoding="utf-8") as template:
    template_html = template.read()

output_html = template_html.replace("{html_table}", supply_tables)

with open("supply_tables.html", "w", encoding="utf-8") as f:
    f.write(output_html)
