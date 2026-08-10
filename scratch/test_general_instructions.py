import json
from app.agents.generation import GenerationAgent, match_subject
from app.agents.validation import ValidationAgent
from app.agents.planning import PlanningAgent

def test_constraints():
    subjects = [
        {"name": "Database Management Systems Lab", "faculty": "Dr. Smith", "type": "Lab", "periods": 3},
        {"name": "Advanced Java", "faculty": "Prof. Alan", "type": "Lecture", "periods": 3},
        {"name": "Web Technologies", "faculty": "Dr. Grace", "type": "Lecture", "periods": 2},
        {"name": "Operating Systems", "faculty": "Prof. John", "type": "Lecture", "periods": 2},
    ]

    print("--- Test 1: Punctuation & Acronym Match ('Schedule Database Lab on Monday.') ---")
    planner = PlanningAgent(
        db=None,
        subjects=subjects,
        department="CSE",
        course="BTech",
        semester=5,
        busy_faculty={},
        ai_instruction="Schedule Database Lab on Monday."
    )
    parsed = planner._parse_instructions_local()
    print(f"Parsed constraints: {parsed}")
    assert len(parsed) == 1, "Failed to parse instruction with punctuation!"
    assert parsed[0]["subject"] == "Database Management Systems Lab"
    assert parsed[0]["day"] == "Monday"
    assert parsed[0]["type"] == "pin_day"

    gen1 = GenerationAgent(subjects, custom_constraints=parsed)
    tt1, logs1 = gen1.generate()
    assert tt1 is not None, "Generation failed"
    monday_dbms = any(slot and match_subject("Database Lab", slot['name']) for slot in tt1["Monday"])
    print(f"Database Lab on Monday? {monday_dbms}")
    assert monday_dbms, "Database Lab was not placed on Monday!"

    print("\n--- Test 2: Day Avoidance ('Avoid Operating Systems on Saturday.') ---")
    planner2 = PlanningAgent(
        db=None,
        subjects=subjects,
        department="CSE",
        course="BTech",
        semester=5,
        busy_faculty={},
        ai_instruction="Avoid Operating Systems on Saturday."
    )
    c2 = planner2._parse_instructions_local()
    gen2 = GenerationAgent(subjects, custom_constraints=c2)
    tt2, logs2 = gen2.generate()
    assert tt2 is not None
    os_on_sat = any(slot and slot['name'] == "Operating Systems" for slot in tt2["Saturday"])
    print(f"Operating Systems on Saturday? {os_on_sat}")
    assert not os_on_sat, "Operating Systems was scheduled on forbidden day Saturday!"

    print("\n--- Test 3: Before Lunch ('Schedule Web Technologies before lunch.') ---")
    planner3 = PlanningAgent(
        db=None,
        subjects=subjects,
        department="CSE",
        course="BTech",
        semester=5,
        busy_faculty={},
        ai_instruction="Schedule Web Technologies before lunch."
    )
    c3 = planner3._parse_instructions_local()
    gen3 = GenerationAgent(subjects, custom_constraints=c3)
    tt3, logs3 = gen3.generate()
    assert tt3 is not None
    web_slots = []
    for day, slots in tt3.items():
        for idx, s in enumerate(slots):
            if s and s['name'] == "Web Technologies":
                web_slots.append((day, idx))
    print(f"Web Technologies slots: {web_slots}")
    all_before_lunch = all(idx < 3 for day, idx in web_slots)
    assert all_before_lunch, "Web Technologies was scheduled after lunch!"

    print("\n--- Test 4: Conflict Diagnosis Test (Faculty 'smith' busy on Monday) ---")
    busy_faculty = {
        "Monday": {
            0: {"smith"}, 1: {"smith"}, 2: {"smith"}, 
            4: {"smith"}, 5: {"smith"}, 6: {"smith"}
        }
    }
    gen_conflict = GenerationAgent(subjects, busy_faculty=busy_faculty, custom_constraints=parsed)
    tt_conflict, logs_conflict = gen_conflict.generate()
    assert tt_conflict is None, "Generation should have failed due to busy faculty"
    report = gen_conflict.last_conflict_report
    print("Conflict Diagnosis Report:")
    print(json.dumps(report, indent=2))
    assert report["subject"] == "Database Management Systems Lab"
    assert "Monday" in report["requested_target"]
    assert len(report["conflict_reasons"]) > 0
    assert len(report["alternative_slots"]) > 0
    print("Conflict Diagnosis Test Passed!")

    print("\nALL INSTRUCTION TEST SCENARIOS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_constraints()
