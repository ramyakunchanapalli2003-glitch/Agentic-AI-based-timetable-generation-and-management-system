from app.agents.planning import PlanningAgent

subjects = [
    {'name': 'Database Management Systems Lab', 'faculty': 'Dr. Smith', 'type': 'Lab', 'periods': 2},
    {'name': 'Operating Systems', 'faculty': 'Dr. Jones', 'type': 'Lecture', 'periods': 3},
    {'name': 'Web Technologies', 'faculty': 'Dr. Patel', 'type': 'Lecture', 'periods': 2},
]

tests = [
    ('Schedule Database Lab on Monday', 'pin_day', 'Monday', 'Database Management Systems Lab'),
    ('Avoid Operating Systems on Saturday', 'avoid_day', 'Saturday', 'Operating Systems'),
    ('Schedule Web Technologies before lunch', 'before_lunch', None, 'Web Technologies'),
    ('Keep Web Technologies on Wednesday', 'pin_day', 'Wednesday', 'Web Technologies'),
]

all_passed = True
for instruction, exp_type, exp_day, exp_subject in tests:
    agent = PlanningAgent(db=None, subjects=subjects, department='CS', course='B.Tech', semester=5,
                          busy_faculty={}, ai_instruction=instruction)
    cs = agent._parse_instructions_local()
    match = any(
        c['type'] == exp_type and
        c['subject'] == exp_subject and
        (exp_day is None or c.get('day') == exp_day)
        for c in cs
    )
    status = 'PASS' if match else 'FAIL'
    if not match:
        all_passed = False
    print(f'[{status}] "{instruction}"')
    print(f'       => {cs}')

print()
print('ALL PASSED' if all_passed else 'SOME TESTS FAILED')
