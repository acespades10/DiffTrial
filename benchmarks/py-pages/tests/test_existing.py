from src.repair import repair

def test_existing():
    assert repair([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]
