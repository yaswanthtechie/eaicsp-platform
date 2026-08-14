import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

import pytest

from src.ensemble import validate_weights



def test_valid_weights():

    assert validate_weights(
        0.3,
        0.7
    ) is True



def test_invalid_weights():

    with pytest.raises(ValueError):

        validate_weights(
            0.5,
            0.8
        )