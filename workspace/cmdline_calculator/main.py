from sys import stdin

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Division by zero")
    return a / b

def main():
    print("Welcome to the Command Line Calculator!")

    while True:
        try:
            a = float(stdin.readline())
            op = stdin.readline().strip()
            b = float(stdin.readline())
            
            if op == '+': 
                result = add(a, b)
            elif op == '-': 
                result = subtract(a, b)
            elif op == '*': 
                result = multiply(a, b)
            elif op == '/': 
                result = divide(a, b)
            else:
                raise ValueError("Unknown operation")
            
            print(f"{a} {op} {b} = {result}")
        except ValueError:
            print("Invalid input. Please enter a number and one of the operations (+, -, *, /)")
        except EOFError:
            break

if __name__ == '__main__':
    main()