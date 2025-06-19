from bs4 import BeautifulSoup
import pandas as pd

# Load the HTML content
with open("Notice Board Summary.html", "r", encoding="utf-8") as file:
    soup = BeautifulSoup(file, "html.parser")

classroom_pattern = r"([A-Za-z]{2}[1-9]{1,2})|SOC|CQ|HSLB"

periods = {
    "MM": "08:30-08:45",
    "1": "08:45-09:40",
    "2": "09:40-10:30",
    "Tut": "10:30-10:45",
    "Tut [1]": "10:45-11:00",
    "Tut [1] [2]": "11:00-11:15",
    "3": "11:15-12:10",
    "4a": "12:10-12:40",
    "4": "12:40-13:10",
    "4c": "13:10-13:40",
    "5": "13:40-14:35",
    "6": "14:35-15:30",
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

# Clean and split room and staff info
import re

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
    if row.get('Times') is not None and row['Times'] != "":
        return row['Times']
    return periods.get(row['Period'])

simplified_sheet['Time'] = simplified_sheet.apply(get_time, axis=1)

# Extract year group for proper sorting (from Activity, assumed to be class names like '10A')
def extract_year(group):
    match = re.match(r"(\d+)", group)
    return int(match.group(1)) if match else 0

simplified_sheet["SortKey"] = simplified_sheet["Activity"].apply(extract_year)

# Sort by Time (chronologically), then by Year group, then by Activity (e.g., A, B...)
simplified_sheet.sort_values(by=["Time", "SortKey", "Activity"], inplace=True)

# Drop the temporary column
simplified_sheet.drop(columns=["SortKey"], inplace=True)

simplified_sheet.drop(columns=["Times"], inplace=True)

html_table = simplified_sheet.to_html(index=False, escape=False, classes="cover-table")

with open("table_template.html", "r", encoding="utf-8") as template:
    templateHtml = template.read()
    html_output = templateHtml.replace("{html_table}", html_table)
    with open("simplified_sheet.html", "w", encoding="utf-8") as f:
        f.write(html_output)
