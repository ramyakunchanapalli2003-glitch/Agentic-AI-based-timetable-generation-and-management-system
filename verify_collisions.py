import sqlite3
import json

def normalize(name):
    if not name: return ""
    return name.strip().lower()

def check_collisions():
    conn = sqlite3.connect('database/timetable.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, department, course, semester, generated_data FROM timetables")
    rows = cursor.fetchall()
    
    faculty_slots = {} # (day, slot_idx) -> list of (tt_id, faculty_name)
    
    collisions = []
    
    for tt_id, dept, course, sem, data_json in rows:
        if not data_json: continue
        data = json.loads(data_json)
        for day, slots in data.items():
            for idx, slot in enumerate(slots):
                if slot and "faculty" in slot:
                    faculty = normalize(slot['faculty'])
                    if faculty == "lunch" or faculty == "": continue
                    
                    key = (day, idx)
                    if key not in faculty_slots:
                        faculty_slots[key] = []
                    
                    for other_tt_id, other_faculty in faculty_slots[key]:
                        if other_faculty == faculty:
                            collisions.append({
                                "day": day,
                                "slot": idx + 1,
                                "faculty": faculty,
                                "tt1": tt_id,
                                "tt2": other_tt_id
                            })
                    
                    faculty_slots[key].append((tt_id, faculty))
    
    conn.close()
    return collisions

if __name__ == "__main__":
    collisions = check_collisions()
    if collisions:
        print(f"Found {len(collisions)} collisions!")
        for c in collisions:
            print(f"Collision on {c['day']} at slot {c['slot']} for faculty '{c['faculty']}' between timetable {c['tt1']} and {c['tt2']}")
    else:
        print("No faculty collisions found!")
