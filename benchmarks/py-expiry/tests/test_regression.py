from src.repair import repair

def test_regression():
    assert repair({'a': 5, 'b': 6, 'c': 5}, 5) == ['b']
    assert repair({}, 0) == []
