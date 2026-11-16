from src.repair import repair

def test_regression():
    assert repair([(100, 0), (6, 2)]) == 6
    import pytest
    with pytest.raises(ValueError):
        repair([(5, 0)])
