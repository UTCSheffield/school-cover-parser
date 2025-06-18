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
    # Skip entirely blank rows
    if all(val == '' for val in values):
        continue
    data.append(values)

# Define column headers manually based on original table
columns = ["Period", "Staff or Room to replace", "Reason", "Activity", "Rooms", "Staff", "Assigned Staff or Room", "Times"]
cover_sheet = pd.DataFrame(data, columns=columns)
cover_sheet = cover_sheet.dropna(subset=["Staff or Room to replace", "Assigned Staff or Room"])
cover_sheet.drop(columns=["Reason", "Times"], inplace=True)
cover_sheet = cover_sheet[~cover_sheet["Assigned Staff or Room"].str.contains("No Cover Required")]
cover_sheet = cover_sheet[~cover_sheet["Period"].str.contains(":Enr")]
cover_sheet = cover_sheet[~cover_sheet["Period"].str.contains("Mon:6")]
cover_sheet = cover_sheet[~cover_sheet["Period"].str.contains("Fri:6")]
cover_sheet = cover_sheet[~cover_sheet["Activity"].str.contains("-")]
cover_sheet = cover_sheet[~cover_sheet["Assigned Staff or Room"].str.contains("No Cover Required", na=False)]
cover_sheet = cover_sheet[cover_sheet["Staff or Room to replace"].str.match(r"([A-Za-z]{2}[1-9]{1,2})|(SOC)|(\([A-Za-z]+, [A-Za-z ]+\))", na=False)]
cover_sheet["Rooms"] = cover_sheet["Rooms"].str.split("; ").str[-1]
cover_sheet["Rooms"] = cover_sheet["Rooms"].str.replace(r"[()]", "", regex=True)
cover_sheet["Staff"] = cover_sheet["Staff"].str.replace(r"[()]", "", regex=True)
cover_sheet.insert(cover_sheet.columns.get_loc("Staff"), "Old Staff", cover_sheet["Staff"].str.split(">", expand=True)[0])
cover_sheet.insert(cover_sheet.columns.get_loc("Staff"), "New Staff", cover_sheet["Staff"].str.split(">", expand=True)[1])
cover_sheet["New Staff"] = cover_sheet["New Staff"].replace("", pd.NA)
cover_sheet["New Staff"] = cover_sheet["New Staff"].fillna(cover_sheet["Old Staff"])
cover_sheet = cover_sheet.drop(columns=["Staff"])
cover_sheet.insert(
    cover_sheet.columns.get_loc("Assigned Staff or Room"),
    "Assigned Staff",
    cover_sheet["Assigned Staff or Room"].str.extract(r"([A-Za-z]+, [A-Za-z ]+)")[0]
)
cover_sheet["Assigned Staff"].fillna("", inplace=True)
cover_sheet.insert(
    cover_sheet.columns.get_loc("Assigned Staff or Room"),
    "Assigned Room",
    cover_sheet["Rooms"].str.split(">", expand=True)[1]
)
cover_sheet["Assigned Room"] = cover_sheet["Assigned Room"].replace("", pd.NA)
cover_sheet["Assigned Room"] = cover_sheet["Assigned Room"].fillna(cover_sheet["Rooms"].str.split(">", expand=True)[0])

print(cover_sheet.tail(20))

"""
changed_classrooms = pd.DataFrame(data, columns=columns)

changed_classrooms = changed_classrooms.drop(columns=["Reason","Times","Rooms"])
changed_classrooms = changed_classrooms.rename(columns={"Staff or Room to replace": "Old Room", "Assigned Staff or Room": "Room"})
changed_classrooms["Old Room"] = changed_classrooms["Old Room"].str.replace(r"[()]", "", regex=True)
changed_classrooms["Staff"] = changed_classrooms["Staff"].str.replace(r"[()]", "", regex=True)
changed_classrooms.insert(changed_classrooms.columns.get_loc("Staff"), "Old Staff", changed_classrooms["Staff"].str.split(">", expand=True)[0])
changed_classrooms.insert(changed_classrooms.columns.get_loc("Staff"), "New Staff", changed_classrooms["Staff"].str.split(">", expand=True)[1])
changed_classrooms = changed_classrooms.drop(columns=["Staff"])
changed_classrooms = changed_classrooms[~changed_classrooms["Activity"].isin(["-"])]
changed_classrooms = changed_classrooms[~changed_classrooms["Room"].str.contains("No Cover Required", na=False)]
changed_classrooms = changed_classrooms[~changed_classrooms["Old Room"].str.contains(r"[A-Za-z]+, [A-Za-z]+", na=False)]
# Replace empty strings and NaN in "New Staff" with values from "Old Staff"
changed_classrooms["New Staff"] = changed_classrooms["New Staff"].replace("", pd.NA)
changed_classrooms["New Staff"] = changed_classrooms["New Staff"].fillna(changed_classrooms["Old Staff"])
changed_classrooms = changed_classrooms.dropna(how='all')
changed_classrooms.reset_index(drop=True, inplace=True)

print(changed_classrooms.tail(20))
"""