from dataclasses import dataclass

@dataclass
class DummyData:
    field1: str
    field2: int

# Dummy data generation
def generate_data():
    return DummyData('test', 42)

if __name__ == '__main__':
    data = generate_data()
    print(data.field1, data.field2)