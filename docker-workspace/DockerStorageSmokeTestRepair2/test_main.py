import pytest

def test_add_positive():
    assert add(2, 3) == 5

def test_add_negative():
    assert add(-1, 2) == 1

def test_add_zero():
    assert add(0, 0) == 0

def test_add_large():
    assert add(1000, 2000) == 3000