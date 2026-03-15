import pytest

from src.LabeledID import LabeledID


@pytest.mark.unit
def test_LID():
    x = "identifier"
    lid = LabeledID(identifier=x, label="label")
    assert not x == lid
    s = set([lid])
    assert x not in s
