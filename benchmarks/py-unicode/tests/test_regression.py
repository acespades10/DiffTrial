from src.repair import repair

def test_regression():
    assert repair(['Straße', 'STRASSE']) == {'strasse': ['Straße', 'STRASSE']}
    assert repair(['é', 'e\u0301']) == {'é': ['é', 'e\u0301']}
