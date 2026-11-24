import pytest

import ytmcp
from ytmcp.__main__ import main


@pytest.mark.unit
def test_version_is_defined() -> None:
    assert ytmcp.__version__ == "0.1.0"


@pytest.mark.unit
def test_main_is_not_implemented_yet() -> None:
    with pytest.raises(SystemExit):
        main()
