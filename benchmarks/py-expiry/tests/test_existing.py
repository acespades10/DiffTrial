from src.repair import repair

def test_existing():
    assert repair({'a': 10, 'b': 2}, 5) == ['a']
