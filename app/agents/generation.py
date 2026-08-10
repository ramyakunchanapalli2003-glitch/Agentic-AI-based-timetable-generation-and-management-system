import random
import re

def match_subject(target_str, subject_name):
    """
    Robust subject name matcher.
    Returns True if target_str matches subject_name via:
    1. Exact match (case-insensitive)
    2. Substring match ("Java" in "Advanced Java")
    3. Acronym match (e.g. "DBMS" -> "Database Management Systems")
    4. Significant token intersection (e.g. "AI" -> "AI Lab", "Web Tech" -> "Web Technologies")
    """
    if not target_str or not subject_name:
        return False
    
    t_raw = target_str.lower().strip()
    s_raw = subject_name.lower().strip()
    
    if t_raw == s_raw or t_raw in s_raw or s_raw in t_raw:
        return True
        
    # Strip punctuation for normalized token comparison
    t = re.sub(r'[^\w\s]', ' ', t_raw).strip()
    s = re.sub(r'[^\w\s]', ' ', s_raw).strip()

    if not t or not s:
        return False

    if t == s or t in s or s in t:
        return True

    s_words = s.split()
    s_acronym = "".join(w[0] for w in s_words if w)
    if t == s_acronym or t_raw == s_acronym:
        return True
        
    if "database" in s and ("dbms" in t or "db" in t):
        return True
        
    t_words = set(t.split())
    s_words_set = set(s_words)
    # Generic words that appear in many subject names and must NOT be used
    # as the sole matching token — they are too ambiguous.
    noise = {
        "lab", "lecture", "subject", "course", "class", "dr", "prof",
        "systems", "system", "management", "advanced", "technology",
        "technologies", "engineering", "science", "introduction", "applied",
        "fundamentals", "theory", "programming", "design", "analysis",
    }
    t_clean = t_words - noise
    s_clean = s_words_set - noise
    
    if t_clean and s_clean and (t_clean & s_clean):
        return True
        
    return False


class GenerationAgent:
    """
    Generates a timetable based on subjects and constraints.
    - Places labs first (continuous slots).
    - Ensures labs don't cross lunch.
    - Fills lectures randomly.
    - Respects period counts and custom natural-language constraints.
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

    def __init__(self, subjects, busy_faculty=None, custom_constraints=None):
        self.subjects = subjects  # List of dicts: {name, faculty, type, periods}
        self.busy_faculty = busy_faculty or {} 
        self.custom_constraints = custom_constraints or []
        self.timetable = {day: [None] * len(self.SLOTS) for day in self.DAYS}
        self.logs = []
        self.last_conflict_report = None

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
        busy_set contains normalized names.
        """
        current_faculties = self._normalize_name(faculty_str)
        for f in current_faculties:
            if f in busy_set:
                return True
        return False

    def log(self, message):
        self.logs.append(message)

    def _get_subject_constraints(self, subject_name):
        """Returns all constraint dicts applicable to subject_name using robust matching."""
        matched = []
        for c in self.custom_constraints:
            target = c.get("subject", "")
            if target and match_subject(target, subject_name):
                matched.append(c)
        return matched

    def _filter_days(self, subject_name, days):
        """Filters candidate days according to pin_day or avoid_day constraints."""
        constraints = self._get_subject_constraints(subject_name)
        allowed = list(days)
        for c in constraints:
            ctype = c.get("type", "")
            target_day = c.get("day", "")
            if target_day:
                target_day_title = target_day.capitalize()
                if ctype == "pin_day":
                    if target_day_title in allowed:
                        allowed = [target_day_title]
                elif ctype == "avoid_day":
                    allowed = [d for d in allowed if d.lower() != target_day.lower()]
        return allowed

    def _filter_slot_indices(self, subject_name, possible_starts, current_block=1):
        """Filters candidate slot start indices based on time_range / before_lunch / after_lunch constraints."""
        constraints = self._get_subject_constraints(subject_name)
        filtered = list(possible_starts)
        for c in constraints:
            ctype = c.get("type", "")
            time_range = c.get("time_range", "")
            time_range_str = time_range.lower() if isinstance(time_range, str) else ""

            if ctype in ("before_lunch", "morning") or time_range_str in ("morning", "before_lunch", "before lunch"):
                filtered = [i for i in filtered if (i + current_block - 1) < self.LUNCH_INDEX]
            elif ctype in ("after_lunch", "afternoon") or time_range_str in ("afternoon", "after_lunch", "after lunch"):
                filtered = [i for i in filtered if i > self.LUNCH_INDEX]
        return filtered

    def analyze_conflict(self, subject):
        """
        Analyzes why placement failed for a subject under custom constraints
        and returns a detailed conflict report with alternative valid slots.
        """
        constraints = self._get_subject_constraints(subject['name'])
        raw_instructions = [c.get('raw_instruction', '') for c in constraints if c.get('raw_instruction')]
        inst_str = "; ".join(raw_instructions) if raw_instructions else "Custom scheduling instruction"

        reasons = []
        target_day = None
        for c in constraints:
            if c.get('day'):
                target_day = c.get('day').capitalize()

        # Check target day capacity, faculty availability & slot availability
        if target_day and target_day in self.DAYS:
            # Check free capacity on target day
            free_slots_count = sum(1 for idx in range(len(self.SLOTS)) if idx != self.LUNCH_INDEX and self.timetable[target_day][idx] is None)
            periods_req = int(subject['periods'])
            if free_slots_count < periods_req:
                reasons.append(f"Insufficient free periods on {target_day} ({free_slots_count} free slot(s) available, but '{subject['name']}' requires {periods_req} period(s)).")

            # Check faculty collisions on target day
            fac_collisions = []
            for slot_idx in range(len(self.SLOTS)):
                if slot_idx == self.LUNCH_INDEX:
                    continue
                if target_day in self.busy_faculty and slot_idx in self.busy_faculty[target_day]:
                    if self._is_faculty_collision(subject['faculty'], self.busy_faculty[target_day][slot_idx]):
                        fac_collisions.append(self.SLOTS[slot_idx])
            
            if fac_collisions:
                reasons.append(
                    f"Faculty '{subject['faculty']}' is double-booked on {target_day} in another department at slot(s): {', '.join(fac_collisions)}."
                )

            # Check if slots are already occupied in current timetable
            occupied_slots = []
            for slot_idx in range(len(self.SLOTS)):
                if slot_idx != self.LUNCH_INDEX and self.timetable[target_day][slot_idx] is not None:
                    occupied_slots.append(f"{self.SLOTS[slot_idx]} ({self.timetable[target_day][slot_idx]['name']})")
            if occupied_slots:
                reasons.append(f"Slots on {target_day} are already occupied by other subjects: {', '.join(occupied_slots)}.")

        if not reasons:
            reasons.append("Insufficient available non-conflicting periods satisfying all time/day preferences.")

        # Find alternative available slots across the week for this subject
        alternatives = []
        is_lab = subject['type'].lower() == 'lab'
        periods = int(subject['periods'])
        block_size = 2 if periods % 2 == 0 else 3
        if periods == 1: block_size = 1
        
        for alt_day in self.DAYS:
            if target_day and alt_day.lower() == target_day.lower():
                continue
            for i in range(len(self.SLOTS) - block_size + 1):
                if i != self.LUNCH_INDEX and (i + block_size - 1) != self.LUNCH_INDEX:
                    if not (i < self.LUNCH_INDEX < i + block_size):
                        free = True
                        for j in range(i, i + block_size):
                            if self.timetable[alt_day][j] is not None:
                                free = False
                                break
                            if alt_day in self.busy_faculty and j in self.busy_faculty[alt_day]:
                                if self._is_faculty_collision(subject['faculty'], self.busy_faculty[alt_day][j]):
                                    free = False
                                    break
                        if free:
                            time_str = f"{self.SLOTS[i].split('-')[0]} to {self.SLOTS[i+block_size-1].split('-')[1]}"
                            alternatives.append(f"{alt_day} ({time_str})")
                            break  # One alternative per day is enough

        return {
            "instruction": inst_str,
            "subject": subject['name'],
            "faculty": subject['faculty'],
            "requested_target": target_day or "Specified time/day",
            "conflict_reasons": reasons,
            "alternative_slots": alternatives[:3]
        }

    def generate(self):
        self.log("GenerationAgent started.")
        self.last_conflict_report = None
        
        # 1. Place Labs (usually 2-3 continuous periods)
        labs = [s for s in self.subjects if s['type'].lower() == 'lab']
        # Prioritize labs with custom constraints so they are scheduled before unconstrained labs
        labs.sort(key=lambda s: 0 if len(self._get_subject_constraints(s['name'])) > 0 else 1)
        for lab in labs:
            periods_needed = int(lab['periods'])
            block_size = 2 if periods_needed % 2 == 0 else 3
            if periods_needed == 1: block_size = 1

            remaining = periods_needed
            attempts = 0
            while remaining > 0 and attempts < 100:
                attempts += 1
                candidate_days = self._filter_days(lab['name'], self.DAYS)
                if not candidate_days:
                    # Only fall back to all days if NO pin/avoid constraint exists.
                    # If a pin_day exists and pinned day has no space, break so
                    # analyze_conflict is triggered with the correct diagnostic.
                    has_pin = any(
                        c.get("type") in ("pin_day", "avoid_day")
                        for c in self._get_subject_constraints(lab['name'])
                    )
                    if has_pin:
                        break  # pinned day is full → will trigger analyze_conflict below
                    candidate_days = list(self.DAYS)

                day = random.choice(candidate_days)
                current_block = min(remaining, block_size)
                
                possible_starts = []
                for i in range(len(self.SLOTS) - current_block + 1):
                    if i != self.LUNCH_INDEX and (i + current_block - 1) != self.LUNCH_INDEX:
                        if not (i < self.LUNCH_INDEX < i + current_block):
                            all_slots_free = True
                            for j in range(i, i + current_block):
                                if self.timetable[day][j] is not None:
                                    all_slots_free = False
                                    break
                                if day in self.busy_faculty and j in self.busy_faculty[day]:
                                    if self._is_faculty_collision(lab['faculty'], self.busy_faculty[day][j]):
                                        all_slots_free = False
                                        break
                            if all_slots_free:
                                possible_starts.append(i)
                
                # Filter start indices by time preferences
                possible_starts = self._filter_slot_indices(lab['name'], possible_starts, current_block)
                
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
                self.last_conflict_report = self.analyze_conflict(lab)
                self.log(f"Failed to place all periods for Lab '{lab['name']}'. Conflict Analysis: {self.last_conflict_report}")
                return None, self.logs

        # 2. Place Lectures
        lectures = [s for s in self.subjects if s['type'].lower() == 'lecture']
        # Prioritize lectures with custom constraints so they are scheduled before unconstrained lectures
        lectures.sort(key=lambda s: 0 if len(self._get_subject_constraints(s['name'])) > 0 else 1)
        for lecture in lectures:
            periods_needed = int(lecture['periods'])
            placed_count = 0
            attempts = 0
            while placed_count < periods_needed and attempts < 500:
                attempts += 1
                candidate_days = self._filter_days(lecture['name'], self.DAYS)
                if not candidate_days:
                    # Only fall back to all days if NO pin/avoid constraint exists.
                    has_pin = any(
                        c.get("type") in ("pin_day", "avoid_day")
                        for c in self._get_subject_constraints(lecture['name'])
                    )
                    if has_pin:
                        continue  # skip this attempt; eventually fails → analyze_conflict
                    candidate_days = list(self.DAYS)

                day = random.choice(candidate_days)
                possible_slots = [i for i in range(len(self.SLOTS)) if i != self.LUNCH_INDEX]
                possible_slots = self._filter_slot_indices(lecture['name'], possible_slots, 1)
                
                if not possible_slots:
                    continue
                    
                slot_idx = random.choice(possible_slots)
                
                if self.timetable[day][slot_idx] is None:
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
                self.last_conflict_report = self.analyze_conflict(lecture)
                self.log(f"Failed to place all periods for Lecture '{lecture['name']}'. Conflict Analysis: {self.last_conflict_report}")
                return None, self.logs
            else:
                self.log(f"Placed all {periods_needed} periods of Lecture '{lecture['name']}'.")

        # Mark Lunch
        for day in self.DAYS:
            self.timetable[day][self.LUNCH_INDEX] = {"name": "LUNCH", "type": "Break"}

        self.log("GenerationAgent completed successfully.")
        return self.timetable, self.logs
