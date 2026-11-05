import sys

from main import add, subtract, multiply, divide

def test_add():
    assert add(2, 3) == 5
    assert add(0, 0) == 0
    assert add(-1, 2) == 1

def test_subtract():
    assert subtract(5, 2) == 3
    assert subtract(1, 1) == 0
    assert subtract(-1, 2) == -3

def test_multiply():
    assert multiply(2, 3) == 6
    assert multiply(-1, 2) == -2
    assert multiply(0, 5) == 0

def test_divide():
    assert divide(10, 2) == 5
    assert divide(8, 4) == 2
    assert divide(6, 3) == 2
    assert divide(10, 0) is None

if __name__ == '__main__':
    test_add()
    test_subtract()
    test_multiply()
    test_divide()