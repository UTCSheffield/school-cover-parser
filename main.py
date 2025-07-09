"""
Script to convert SIMS Notice Board Summary to a nicer output
"""
import os
from pathlib import Path
import webbrowser
import re
from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd
from win32com import client
# from playwright.sync_api import sync_playwright
# from PIL import Image

# PARAMETERS
DO_EMAIL = False
# PARAMETERS END

# CONSTANTS
DATA_FILENAME = "Notice Board Summary.html"
OUTPUTS_FOLDER = "outputs"
TEMPLATES_FOLDER = "templates"
PERIODS = {
    "MM": {"time": "08:30-08:45", "label": "MM"},
    "1": {"time": "08:45-09:40", "label": "1"},
    "2": {"time": "09:40-10:30", "label": "2"},
    "Tut": {"time": "10:30-10:45", "label": "Tutor A"},
    "Tut [1]": {"time": "10:45-11:00", "label": "Tutor B"},
    "Tut [1] [2]": {"time": "11:00-11:15", "label": "Tutor C"},
    "3": {"time": "11:15-12:10", "label": "3"},
    "4a": {"time": "12:10-12:40", "label": "4a"},
    "4": {"time": "12:40-13:10", "label": "4b"},
    "4c": {"time": "13:10-13:40", "label": "4c"},
    "5": {"time": "13:40-14:35", "label": "5"},
    "6": {"time": "14:35-15:30", "label": "6"},
}
SUBJECT_DF = pd.read_csv("class_codes_departments.csv")
SUBJECT_DICT = dict(zip(SUBJECT_DF["Code"], SUBJECT_DF["Department"]))
CLASSROOM_PATTERN = r"([A-Za-z]{2}[1-9]{1,2})|SOC|CQ|HS[LD]B|TLV"
STAFF_PATTERN = r"[A-Za-z]+, [A-Za-z ]+"
COLUMNS = [
    "Period", "Staff or Room to replace", "Reason", "Activity",
    "Rooms", "Staff", "Assigned Staff or Room", "Times"
]
# CONSTANTS END

# LOAD DATA
data_file_path = Path.joinpath(Path.home(), "Downloads", DATA_FILENAME)

if not Path(data_file_path).is_file():
    data_file_path = Path.joinpath(Path.cwd(), "test_data", DATA_FILENAME)
    if not Path(data_file_path).is_file():
        raise ValueError("Data file not found.")

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
date_text = ""  # pylint: disable=C0103
for string in soup.stripped_strings:
    if "Full List of Staff and Room Details:" in string:
        match = re.search(r"Full List of Staff and Room Details:" +
                          r"\s*(\d{1,2}-[A-Za-z]{3}-\d{4})", string)
        if match:
            date_text = match.group(1)
            break

formatted_date = "Unknown Date"  # pylint: disable=C0103

if date_text:
    try:
        date_obj = datetime.strptime(date_text, "%d-%b-%Y")
        formatted_date = date_obj.strftime("%A %d %B %Y")
    except ValueError:
        formatted_date = date_text
# DATE EXTRACTION END

# DATAFRAME + CLEANUP
cover_sheet = pd.DataFrame(data, columns=COLUMNS)

cover_sheet = cover_sheet.dropna(subset=["Staff or Room to replace",
                                         "Assigned Staff or Room"])
cover_sheet.drop(columns=["Reason"], inplace=True)
cover_sheet = cover_sheet[~cover_sheet["Assigned Staff or Room"]
                          .str.contains("No Cover Required", na=False)]
cover_sheet = cover_sheet[~cover_sheet["Period"]
                          .str.contains(":Enr|Mon:6|Fri:6")]
cover_sheet = cover_sheet[~cover_sheet["Activity"]
                          .str.contains("-")]

cover_sheet["Rooms"] = cover_sheet["Rooms"].str.replace(r"[()]", "",
                                                        regex=True)
cover_sheet["Staff or Room to replace"] = (
    cover_sheet["Staff or Room to replace"].str.replace(r"[()]", "",
                                                        regex=True))
# DATAFRAME + CLEANUP END

# FUNCTIONS


def header(text, colspan):
    return f"""
    <thead>
        <tr>
            <th colspan="{colspan}" style="font-size: 24px; padding: 10px;">
                {text}
            </th>
        </tr>
    """


def email(subject, body, to=""):
    outlook = client.Dispatch('Outlook.Application')
    message = outlook.CreateItem(0)
    message.Subject = subject
    message.To = to
    message.HTMLBody = body
    message.Display()


def get_template():
    '''Returns the HTML template'''
    template_path = Path.joinpath(Path.cwd(), TEMPLATES_FOLDER,
                              "table_template.html")
    with open(template_path, "r", encoding="utf-8") as template:
        return template.read()


def save_output(content, filename):
    '''Function to save output to a file'''
    output_path = Path.joinpath(Path.cwd(), OUTPUTS_FOLDER, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


def get_dept(activity):
    dept_match = re.search(r"\/([A-Za-z]+)\d", activity)
    if match:
        dept_code = dept_match.group(1)
        dept = SUBJECT_DICT.get(dept_code, "<strong><p color='red'>Unknown Department</p></strong>")
        return dept
    return ""


def get_staff_initials(name):
    initial_match = re.match(r"([A-Za-z]+),\s+[A-Za-z]+\s+([A-Za-z])", name)
    if initial_match:
        last_name = initial_match.group(1)
        first_initial = initial_match.group(2).upper()
        last_initial = last_name[0].upper()
        last_second_initial = last_name[1].upper()
        initials = f"{first_initial}{last_initial}{last_second_initial}"
        return f"{name} ({initials})"
    return name


def room_or_supply(data: pd.DataFrame, supply=False):
    uniques = sorted(data["Assigned Staff"].unique()) if supply else sorted(data["Replaced Room"].unique())
    tables = []
    for unique in uniques:
        filtered = data[data["Assigned Staff"] == unique].copy() if supply is True else data[data["Replaced Room"] == unique].copy()

        # Get periods that are already assigned for this supply
        assigned_periods = set(filtered["Period"])

        # Fill in missing periods
        missing = [p for p in PERIODS.values() if p['label'] not in assigned_periods]

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
                }]) if supply else pd.DataFrame([{
                    "Day": "",
                    "Period": label,
                    "Activity": "",
                    "Assigned Room": "",
                    "Time": time
                }])
            ], ignore_index=True)

        filtered["SortKey"] = filtered["Time"]
        filtered.sort_values(by="SortKey", inplace=True)
        filtered.drop(columns=["SortKey"], inplace=True)

        if filtered.empty:
            continue

        filtered.insert(
            filtered.columns.get_loc("Teacher to Cover"),
            "Department",
            filtered["Activity"].apply(get_dept)
        ) if supply else ""

        filtered["Teacher to Cover"] = filtered["Teacher to Cover"].apply(get_staff_initials) if supply else ""

        table_html = filtered.to_html(
            index=False,
            escape=False,
            classes=["cover-table", "supply-table" if supply else "room-table"],
            columns=["Period", "Activity", "Teacher to Cover", "Department", "Room", "Time"] if supply else ["Period", "Activity", "Assigned Room"],
        ).replace(
            "<thead>",
            header(f"{unique} Cover Assignments - {formatted_date}" if supply else f"Room Changes for {unique} - {formatted_date}", 6 if supply else 3)
        )

        tables.append(table_html)

        """if supply == False:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 300, "height": 400})
                page = context.new_page()
                page.set_content(get_template().replace("{table}", table_html), wait_until='networkidle')
                page.screenshot(path=Path.joinpath(Path.cwd(), outputs_folder, f"{unique}.png"), clip={"x": 0, "y": 0, "width": 300, "height": 400})
                browser.close()

            path = Path.cwd() / outputs_folder / f"{unique}.png"

            with Image.open(path) as img:
                # Rotate the image 90 degrees clockwise
                #img = img.rotate(-90, expand=True)

                # Convert to grayscale (equivalent to setting type = 'grayscale' and colorspace = 'gray')
                img = img.convert("L")  # "L" = 8-bit pixels, black and white

                # Quantize to 256 grayscale colors (Pillow will do this automatically after conversion to 'L')
                img = img.quantize(colors=256, method=Image.FASTOCTREE)

                # Remove alpha channel by pasting onto white background if it exists
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and 'transparency' in img.info):
                    background = Image.new("L", img.size, 255)  # White background in grayscale
                    img = Image.composite(img.convert("L"), background, img.convert("L"))

                # Save the modified image (overwrites original)
                img.save(path)"""
    return tables


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
# FUNCTIONS END


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

# Simplified DataFrame start

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

# ABOVE IS CONSISTENT FOR ALL TABLES

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

html_table = html_table.replace(
    "<thead>",
    header(f"Cover and Room Change Summary<br>{formatted_date}", 7 if "Times" in simplified_sheet.columns else 6)
)

html_output = get_template().replace("{table}", html_table)
cover_output_path = save_output(html_output, "cover_sheet.html")

if do_email:
    email(
        subject=f"Cover & Room Change Summary - {formatted_date}",
        body=html_output,
        to="allutcolpstaff@utcsheffield.org.uk")
else:
    webbrowser.open(cover_output_path)

supply_rooms = room_or_supply(
    simplified_sheet[simplified_sheet["Assigned Staff"].str.match(r"Supply \d+", na=False)].rename(columns={"Replaced Staff": "Teacher to Cover", "Assigned Room": "Room"}, inplace=False),
    supply=True
) + room_or_supply(
    simplified_sheet[simplified_sheet["Replaced Room"].str.match(classroom_pattern, na=False)],
    supply=False
)

supply_room_html = "<br><br>".join(supply_rooms)

output_html = get_template().replace("{table}", supply_room_html)

supply_output_path = save_output(output_html, "supply_sheet.html")

webbrowser.open(supply_output_path)

os.rename(data_file_path, str(data_file_path).replace("Notice Board Summary", f"Notice Board Summary_{date_text}")) if "test_data" not in str(data_file_path) else ""
