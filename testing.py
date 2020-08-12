# A test file to be run after code modifications
# `py.test testing.py`

from convert import *

def test_setpartsequal1():
    ft = FileTag("artist", "ALBUM", "tit Le")
    assert ft.set_parts_equal(artist="artist", album="ALBUM", title="tit Le")

def test_setpartsequal2():
    ar="artist"; al="ALBUM"; tit="";
    assert FileTag(ar,al,tit).set_parts_equal(artist=ar, album=al, title=tit)
