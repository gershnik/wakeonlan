# pylint: disable=missing-function-docstring, missing-module-docstring, use-implicit-booleaness-not-comparison

from wakeonlan import get_names, save_name, get_name_record, delete_name


def test_save():
    assert get_names() == {}
    save_name("test", (1,1,1,1,1,1), "127.0.0.1", 9)
    rec = get_name_record("test")
    assert not rec is None
    assert len(rec) == 2
    assert rec[0] == [1,1,1,1,1,1]
    assert rec[1] == ("127.0.0.1", 9)
    assert get_names() == {
        "test": ([1,1,1,1,1,1], ("127.0.0.1", 9))
    }
    delete_name("test")
    assert get_names() == {}
    assert get_name_record("test") is None

