from src.config import should_promote


def test_should_promote():
    assert not should_promote(0.60)
    assert not should_promote(0.84)

    assert should_promote(0.85)
    assert should_promote(0.99)