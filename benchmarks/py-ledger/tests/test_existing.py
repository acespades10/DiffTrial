from src.repair import repair

def test_existing():
    assert repair([{'amount': 3}, {'amount': None}]) == [{'amount': 3}]
