from src.repair import repair

def test_regression():
    assert repair([{'amount': 0}, {'amount': -2}, {}]) == [{'amount': 0}, {'amount': -2}]
