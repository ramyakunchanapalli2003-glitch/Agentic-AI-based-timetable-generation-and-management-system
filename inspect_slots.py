import sqlite3, json

conn = sqlite3.connect('database/timetable.db')
cur = conn.cursor()
cur.execute('SELECT id, generated_data FROM timetables LIMIT 1')
row = cur.fetchone()
if row:
    tt_id, data_raw = row
    data = json.loads(data_raw)
    for day in data:
        for i, slot in enumerate(data[day]):
            if slot and 'faculty' in slot:
                print(f"Timetable {tt_id}: {day} Slot {i} (0-indexed) has Faculty: {slot['faculty']}")
                break
        else: continue
        break
else:
    print("No timetables found.")
conn.close()
