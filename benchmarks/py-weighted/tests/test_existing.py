from src.repair import repair

def test_existing():
    assert repair([(10, 1), (20, 1)]) == 15
