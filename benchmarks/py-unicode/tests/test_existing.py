from src.repair import repair

def test_existing():
    assert repair(['Ace', 'ACE']) == {'ace': ['Ace', 'ACE']}
