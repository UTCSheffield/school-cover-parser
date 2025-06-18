from bs4 import BeautifulSoup
import pandas as pd

# Load the HTML content
with open("Notice Board Summary.html", "r", encoding="utf-8") as file:
    soup = BeautifulSoup(file, "html.parser")

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
cover_sheet.drop(columns=["Reason", "Times"], inplace=True)
cover_sheet = cover_sheet[~cover_sheet["Assigned Staff or Room"].str.contains("No Cover Required", na=False)]
cover_sheet = cover_sheet[~cover_sheet["Period"].str.contains(":Enr|Mon:6|Fri:6")]
cover_sheet = cover_sheet[~cover_sheet["Activity"].str.contains("-")]

# Filter valid staff/room replacements
pattern = r"([A-Za-z]{2}[1-9]{1,2})|(SOC)|(\([A-Za-z]+, [A-Za-z ]+\))"
cover_sheet = cover_sheet[cover_sheet["Staff or Room to replace"].str.match(pattern, na=False)]
cover_sheet["Staff or Room to replace"] = cover_sheet["Staff or Room to replace"].str.replace(r"[()]", "", regex=True)

# Clean and split room and staff info
cover_sheet["Rooms"] = cover_sheet["Rooms"].str.split("; ").str[-1].str.replace(r"[()]", "", regex=True)

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
cover_sheet["Assigned Room"] = cover_sheet["Assigned Room"].fillna(cover_sheet["Assigned Staff or Room"].str.split(">", expand=True)[0])

# Display the last 20 rows
#print(cover_sheet.tail(20))

simplified_sheet = cover_sheet
simplified_sheet.drop(columns=["Staff", "Rooms", "Assigned Staff or Room"], inplace=True)

simplified_sheet = simplified_sheet.sort_values(by=["Period", "Activity"], kind="stable")
html_table = simplified_sheet.to_html(index=False, escape=False, classes="cover-table")

with open("table_template.html", "r", encoding="utf-8") as template:
    templateHtml = template.read()
    html_output = templateHtml.replace("{html_table}", html_table)
    with open("simplified_sheet.html", "w", encoding="utf-8") as f:
        f.write(html_output)
