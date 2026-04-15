class ValidationAgent:
    """
    Validates a generated timetable against rules:
    - Lab continuity (actually checked by GenAgent, but good to verify).
    - No subject in lunch.
    - One subject per slot (implied if not missing).
    - Exact weekly period count match.
    """
    
    LUNCH_INDEX = 3

    def __init__(self, subjects, timetable, busy_faculty=None):
        self.subjects = subjects
        self.timetable = timetable
        self.busy_faculty = busy_faculty or {}
        self.logs = []

    def _normalize_name(self, name):
        """
        Cleans faculty names: lowercase, removes common titles, strips spaces.
        Returns a set of normalized names to handle 'Faculty A, Faculty B'.
        """
        if not name: return set()
        
        # Split by common delimiters
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
        # Every lab period should be part of a block of at least size 2.
        # This is a bit complex for a simple validator, so we check if any lab is isolated (just 1 slot surrounded by non-lab).
        for day, slots in self.timetable.items():
            for i, slot in enumerate(slots):
                if slot and slot['type'] == 'Lab':
                    # Check if it has a neighbor of the same name
                    has_neighbor = False
                    if i > 0 and slots[i-1] and slots[i-1]['name'] == slot['name']:
                        has_neighbor = True
                    if i < len(slots) - 1 and slots[i+1] and slots[i+1]['name'] == slot['name']:
                        has_neighbor = True
                    
                    # Special case: if target periods for the lab is 1, it's allowed.
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

        self.log("ValidationAgent passed successfully.")
        return True, self.logs
