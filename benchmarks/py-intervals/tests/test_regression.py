from src.repair import repair

def test_regression():
    assert repair([[4, 7], [1, 4], [9, 9]]) == [[1, 7], [9, 9]]
    assert repair([]) == []
