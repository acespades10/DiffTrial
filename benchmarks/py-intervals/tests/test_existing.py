from src.repair import repair

def test_existing():
    assert repair([[1, 3], [2, 4]]) == [[1, 4]]
