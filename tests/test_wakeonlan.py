# pylint: disable=missing-function-docstring, missing-module-docstring, use-implicit-booleaness-not-comparison

from wakeonlan import get_names, save_name, get_name_record, delete_name, HostRecord


def test_save():
    assert get_names() == {}
    save_name("test", HostRecord((1,1,1,1,1,1), None, "127.0.0.1", 9))
    rec = get_name_record("test")
    assert rec == HostRecord((1,1,1,1,1,1), None, "127.0.0.1", 9)
    assert get_names() == {
        "test": HostRecord((1,1,1,1,1,1), None, "127.0.0.1", 9)
    }
    delete_name("test")
    assert get_names() == {}
    assert get_name_record("test") is None

    save_name("test", HostRecord((1,1,1,1,1,1), "eth0", None, 10))
    rec = get_name_record("test")
    assert rec == HostRecord((1,1,1,1,1,1), "eth0", None, 10)
    assert get_names() == {
        "test": HostRecord((1,1,1,1,1,1), "eth0", None, 10)
    }
    delete_name("test")
    assert get_names() == {}
    assert get_name_record("test") is None

    save_name("test", HostRecord((1,1,1,1,1,1), None, "255.255.255.255", 9))
    rec = get_name_record("test")
    assert rec == HostRecord((1,1,1,1,1,1), None, None, 9)
    assert get_names() == {
        "test": HostRecord((1,1,1,1,1,1), None, None, 9)
    }
    delete_name("test")
    assert get_names() == {}
    assert get_name_record("test") is None

