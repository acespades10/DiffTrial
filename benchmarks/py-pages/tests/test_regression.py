from src.repair import repair

def test_regression():
    assert repair([1, 2, 3], 2) == [[1, 2], [3]]
    assert repair([1], 3) == [[1]]
    assert repair([], 2) == []
