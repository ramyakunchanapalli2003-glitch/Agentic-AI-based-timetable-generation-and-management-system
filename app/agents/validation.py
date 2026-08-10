from app.agents.generation import match_subject

class ValidationAgent:
    """
    Validates a generated timetable against rules:
    - Lab continuity.
    - No subject in lunch.
    - Exact weekly period count match.
    - Global faculty collision check.
    - Custom natural-language instruction constraint verification.
    """
    
    LUNCH_INDEX = 3

    def __init__(self, subjects, timetable, busy_faculty=None, custom_constraints=None):
        self.subjects = subjects
        self.timetable = timetable
        self.busy_faculty = busy_faculty or {}
        self.custom_constraints = custom_constraints or []
        self.logs = []

    def _normalize_name(self, name):
        """
        Cleans faculty names: lowercase, removes common titles, strips spaces.
        Returns a set of normalized names to handle 'Faculty A, Faculty B'.
        """
        if not name: return set()
        
        raw_names = []
        for delimiter in [',', '&', ' and ']:
            if delimiter in name:
                if not raw_names:
                    raw_names = [n.strip() for n in name.split(delimiter)]
                else:
                    new_names = []
                    for rn in raw_names:
                        new_names.extend([n.strip() for n in rn.split(delimiter)])
                    raw_names = new_names
        
        if not raw_names:
            raw_names = [name.strip()]

        normalized = set()
        titles = ["dr.", "prof.", "mr.", "mrs.", "ms.", "er."]
        
        for n in raw_names:
            n_clean = n.lower()
            for title in titles:
                if n_clean.startswith(title):
                    n_clean = n_clean[len(title):].strip()
            if n_clean:
                normalized.add(n_clean)
        
        return normalized

    def _is_faculty_collision(self, faculty_str, busy_set):
        """
        Checks if ANY of the faculty in faculty_str is in the busy_set.
        """
        current_faculties = self._normalize_name(faculty_str)
        for f in current_faculties:
            if f in busy_set:
                return True
        return False

    def log(self, message):
        self.logs.append(message)

    def validate(self):
        self.log("ValidationAgent started.")
        
        # 1. Total counts
        counts = {s['name']: 0 for s in self.subjects}
        for day, slots in self.timetable.items():
            for i, slot in enumerate(slots):
                if slot and slot['name'] != "LUNCH":
                    if slot['name'] in counts:
                        counts[slot['name']] += 1
                    else:
                        self.log(f"Error: Unknown subject '{slot['name']}' found in timetable.")
                        return False, self.logs

        for s in self.subjects:
            if counts[s['name']] != int(s['periods']):
                self.log(f"Error: Period count mismatch for '{s['name']}'. Expected {s['periods']}, got {counts[s['name']]}.")
                return False, self.logs

        # 2. Lunch slot empty (only marked "LUNCH")
        for day, slots in self.timetable.items():
            if slots[self.LUNCH_INDEX]['name'] != "LUNCH":
                self.log(f"Error: Subject found in lunch slot on {day}.")
                return False, self.logs

        # 3. Lab continuity
        for day, slots in self.timetable.items():
            for i, slot in enumerate(slots):
                if slot and slot['type'] == 'Lab':
                    has_neighbor = False
                    if i > 0 and slots[i-1] and slots[i-1]['name'] == slot['name']:
                        has_neighbor = True
                    if i < len(slots) - 1 and slots[i+1] and slots[i+1]['name'] == slot['name']:
                        has_neighbor = True
                    
                    target_periods = next(int(s['periods']) for s in self.subjects if s['name'] == slot['name'])
                    if not has_neighbor and target_periods > 1:
                        self.log(f"Error: Isolated lab session for '{slot['name']}' on {day}.")
                        return False, self.logs

        # 4. Cross-timetable Faculty Collision Check
        for day, slots in self.timetable.items():
            for idx, slot in enumerate(slots):
                if slot and "faculty" in slot:
                    if day in self.busy_faculty and idx in self.busy_faculty[day]:
                        if self._is_faculty_collision(slot['faculty'], self.busy_faculty[day][idx]):
                            self.log(f"Error: Faculty collision for '{slot['faculty']}' on {day} at slot {idx+1} with another class.")
                            return False, self.logs

        # 5. Custom Natural-Language Constraint Verification
        for c in self.custom_constraints:
            target_sub = c.get("subject", "")
            ctype = c.get("type", "")
            target_day = c.get("day", "")
            time_range = c.get("time_range", "")
            time_range_str = time_range.lower() if isinstance(time_range, str) else ""

            if not target_sub:
                continue

            for day, slots in self.timetable.items():
                for idx, slot in enumerate(slots):
                    if slot and slot['name'] != "LUNCH":
                        if match_subject(target_sub, slot['name']):
                            if ctype == "pin_day" and target_day and day.lower() != target_day.lower():
                                self.log(f"Error: Custom constraint failed: Subject '{slot['name']}' was scheduled on {day} instead of requested day {target_day.capitalize()}.")
                                return False, self.logs
                            if ctype == "avoid_day" and target_day and day.lower() == target_day.lower():
                                self.log(f"Error: Custom constraint failed: Subject '{slot['name']}' was scheduled on forbidden day {target_day.capitalize()}.")
                                return False, self.logs
                            if (ctype in ("before_lunch", "morning") or time_range_str in ("morning", "before_lunch", "before lunch")) and idx > self.LUNCH_INDEX:
                                self.log(f"Error: Custom constraint failed: Subject '{slot['name']}' was scheduled after lunch at slot {idx+1} instead of morning/before lunch.")
                                return False, self.logs
                            if (ctype in ("after_lunch", "afternoon") or time_range_str in ("afternoon", "after_lunch", "after lunch")) and idx < self.LUNCH_INDEX:
                                self.log(f"Error: Custom constraint failed: Subject '{slot['name']}' was scheduled before lunch at slot {idx+1} instead of afternoon/after lunch.")
                                return False, self.logs

        self.log("ValidationAgent passed successfully.")
        return True, self.logs
