from wakeonlan import *

def test_save():
    assert getNames() == {}
    saveName("test", (1,1,1,1,1,1), "127.0.0.1", 9)
    rec = getNameRecord("test")
    assert not rec is None
    assert len(rec) == 2
    assert rec[0] == [1,1,1,1,1,1]
    assert rec[1] == ("127.0.0.1", 9)
    assert getNames() == {
        "test": ([1,1,1,1,1,1], ("127.0.0.1", 9))
    }
    deleteName("test")
    assert getNames() == {}
    assert getNameRecord("test") == None

