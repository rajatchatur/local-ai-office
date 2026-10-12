from flask import Flask, request, jsonify
from datetime import datetime
import requests
import json

app = Flask(__name__)

# Weather API
WEATHER_API = 'https://api.weatherapi.com/v1/current.json?q={city}&key={API_KEY}'

# Place suggestions
PLACE_SUGGESTIONS = {
    'Paris': ['Eiffel Tower', 'Louvre Museum', 'Champs-Élysées'],
    'Cancun': ['Museo Nacional de Antropología', 'Playa del Carmen'],
    'São Paulo': ['Parque São Cristóvão', 'Ibirapuera Park']
}

# Local food suggestions
LOCAL_FOOD_SUGGESTIONS = {
    'Paris': ['Pain au chocolat', 'Tarte Tatin'],
    'Cancun': ['Tortilla de Patatas', 'Ceviche'],
    'São Paulo': ['Pão de queijo', 'Ceviche']
}

@app.route('/suggest', methods=['GET'])
def suggest():
    city = request.args.get('city')
    if not city:
        return jsonify({'error': 'Please provide a city'}), 400

    # Weather API
    response = requests.get(WEATHER_API.format(city=city, API_KEY='YOUR_API_KEY'))
    data = response.json()
    weather = data['current']['condition']['text']

    # Place suggestions
    places = PLACE_SUGGESTIONS.get(city, [])
    if not places:
        return jsonify({'error': 'No places found for this city'}), 404

    # Food suggestions
    foods = LOCAL_FOOD_SUGGESTIONS.get(city, [])
    if not foods:
        return jsonify({'error': 'No food suggestions found'}), 404

    return jsonify({
        'places': places,
        'foods': foods,
        'weather': weather
    })

if __name__ == '__main__':
    app.run(debug=True)