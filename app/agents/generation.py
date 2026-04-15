import random

class GenerationAgent:
    """
    Generates a timetable based on subjects and constraints.
    - Places labs first (continuous slots).
    - Ensures labs don't cross lunch.
    - Fills lectures randomly.
    - Respects period counts.
    """
    
    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    SLOTS = [
        "09:30-10:30",
        "10:30-11:30",
        "11:30-12:30",
        "12:30-02:00", # LUNCH
        "02:00-03:00",
        "03:00-04:00",
        "04:00-05:00"
    ]
    LUNCH_INDEX = 3

    def __init__(self, subjects, busy_faculty=None):
        self.subjects = subjects  # List of dicts: {name, faculty, type, periods}
        # busy_faculty: day -> slot_idx -> set of normalized faculty names
        self.busy_faculty = busy_faculty or {} 
        self.timetable = {day: [None] * len(self.SLOTS) for day in self.DAYS}
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
                # This is a bit naive but covers most cases
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
        busy_set contains normalized names.
        """
        current_faculties = self._normalize_name(faculty_str)
        for f in current_faculties:
            if f in busy_set:
                return True
        return False

    def log(self, message):
        self.logs.append(message)

    def generate(self):
        self.log("GenerationAgent started.")
        
        # 1. Place Labs (usually 2-3 continuous periods)
        labs = [s for s in self.subjects if s['type'].lower() == 'lab']
        for lab in labs:
            periods_needed = int(lab['periods'])
            placed = False
            
            # Try to find a continuous block for the lab
            # We'll try to place all periods of a lab in one day if possible, 
            # or split them into blocks of 2 or 3 if they are many.
            # For simplicity in this project, we assume lab periods are delivered in blocks.
            
            # Standard Lab Block size is usually 2 or 3.
            block_size = 2 if periods_needed % 2 == 0 else 3
            if periods_needed == 1: block_size = 1

            remaining = periods_needed
            attempts = 0
            while remaining > 0 and attempts < 100:
                attempts += 1
                day = random.choice(self.DAYS)
                current_block = min(remaining, block_size)
                
                # Possible start indices (cannot cross lunch)
                # Before lunch: 0, 1, 2
                # After lunch: 4, 5, 6
                possible_starts = []
                for i in range(len(self.SLOTS) - current_block + 1):
                    if i != self.LUNCH_INDEX and (i + current_block - 1) != self.LUNCH_INDEX:
                        # Check if lunch is in between
                        if not (i < self.LUNCH_INDEX < i + current_block):
                           # Check if slots are free in CURRENT timetable
                           # AND faculty is free in OTHER timetables
                           all_slots_free = True
                           for j in range(i, i + current_block):
                               if self.timetable[day][j] is not None:
                                   all_slots_free = False
                                   break
                               
                               # Check busy_faculty for other timetables
                               if day in self.busy_faculty and j in self.busy_faculty[day]:
                                   if self._is_faculty_collision(lab['faculty'], self.busy_faculty[day][j]):
                                       all_slots_free = False
                                       break
                           
                           if all_slots_free:
                               possible_starts.append(i)
                
                if possible_starts:
                    start = random.choice(possible_starts)
                    for j in range(start, start + current_block):
                        self.timetable[day][j] = {
                            "name": lab['name'],
                            "faculty": lab['faculty'],
                            "type": "Lab"
                        }
                    remaining -= current_block
                    self.log(f"Placed {current_block} periods of Lab '{lab['name']}' on {day} at slot {start+1}.")
            
            if remaining > 0:
                self.log(f"Failed to place all periods for Lab '{lab['name']}'.")
                return None, self.logs

        # 2. Place Lectures
        lectures = [s for s in self.subjects if s['type'].lower() == 'lecture']
        for lecture in lectures:
            periods_needed = int(lecture['periods'])
            placed_count = 0
            attempts = 0
            while placed_count < periods_needed and attempts < 500:
                attempts += 1
                day = random.choice(self.DAYS)
                slot_idx = random.choice([i for i in range(len(self.SLOTS)) if i != self.LUNCH_INDEX])
                
                if self.timetable[day][slot_idx] is None:
                    # Check busy_faculty for other timetables
                    is_faculty_busy = False
                    if day in self.busy_faculty and slot_idx in self.busy_faculty[day]:
                        if self._is_faculty_collision(lecture['faculty'], self.busy_faculty[day][slot_idx]):
                            is_faculty_busy = True
                    
                    if not is_faculty_busy:
                        self.timetable[day][slot_idx] = {
                            "name": lecture['name'],
                            "faculty": lecture['faculty'],
                            "type": "Lecture"
                        }
                        placed_count += 1
            
            if placed_count < periods_needed:
                self.log(f"Failed to place all periods for Lecture '{lecture['name']}'.")
                return None, self.logs
            else:
                self.log(f"Placed all {periods_needed} periods of Lecture '{lecture['name']}'.")

        # Mark Lunch
        for day in self.DAYS:
            self.timetable[day][self.LUNCH_INDEX] = {"name": "LUNCH", "type": "Break"}

        self.log("GenerationAgent completed successfully.")
        return self.timetable, self.logs
