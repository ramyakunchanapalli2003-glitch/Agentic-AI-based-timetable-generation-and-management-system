from app.agents.generation import GenerationAgent

def test_normalization():
    agent = GenerationAgent([])
    
    # Test cases: (input_string, expected_set)
    test_cases = [
        ("Dr. Smith", {"smith"}),
        ("Prof. Johnson", {"johnson"}),
        ("Mr. Ray", {"ray"}),
        ("Ms.  Alice ", {"alice"}),
        ("Dr. Smith, Prof. Johnson", {"smith", "johnson"}),
        ("Alice & Bob", {"alice", "bob"}),
        ("Alice and Bob", {"alice", "bob"}),
        ("Er. Brown", {"brown"}),
        ("Mrs. Davis", {"davis"}),
    ]
    
    for input_str, expected in test_cases:
        result = agent._normalize_name(input_str)
        assert result == expected, f"Failed for '{input_str}': expected {expected}, got {result}"
    
    print("Normalization tests passed!")

def test_collision_detection():
    # busy_faculty: day -> slot_idx -> set of normalized faculty names
    busy = {
        "Monday": {0: {"smith", "johnson"}}
    }
    agent = GenerationAgent([], busy_faculty=busy)
    
    # Collision cases
    assert agent._is_faculty_collision("Dr. Smith", busy["Monday"][0]) == True
    assert agent._is_faculty_collision("Prof. Johnson", busy["Monday"][0]) == True
    assert agent._is_faculty_collision("Dr. Smith & Alice", busy["Monday"][0]) == True
    
    # No collision cases
    assert agent._is_faculty_collision("Alice", busy["Monday"][0]) == False
    assert agent._is_faculty_collision("Dr. Ray", busy["Monday"][0]) == False
    
    print("Collision detection tests passed!")

if __name__ == "__main__":
    try:
        test_normalization()
        test_collision_detection()
        print("All verification tests passed!")
    except AssertionError as e:
        print(f"Verification failed: {e}")
