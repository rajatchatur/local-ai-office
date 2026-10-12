from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/recommend', methods=['POST'])
def recommend_food():
    data = request.get_json()
    ingredients = data.get('ingredients', [])

    # Simple recommendation logic
    if 'cheese' in ingredients:
        return jsonify(foods=['Cheese Pizza', 'Cheeseburger'])
    elif 'bread' in ingredients:
        return jsonify(foods=['Toast', 'Sandwich'])
    else:
        return jsonify(foods=['Omelette', 'Salad'])

if __name__ == '__main__':
    app.run(debug=True)