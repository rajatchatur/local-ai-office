from flask import Flask, request, jsonify
from flask_restful import Resource, Api
from datetime import datetime
import json

app = Flask(__name__)
api = Api(app)

# Sample data
places = {
    "Paris": {
        "weather": "Sunny",
        "activities": ["Eiffel Tower", "Louvre Museum", "Seine River Cruise"]
    },
    "Santiago": {
        "weather": "Cloudy",
        "activities": ["Atacama Desert", "Cathedral of the Americas"]
    }
}

# Weather data
weather_data = {
    "Paris": 22, 
    "Santiago": 18
}

# Sample endpoint
class TravelSuggest(Resource):
    def get(self):
        location = request.args.get('location')
        weather = weather_data.get(location, 15)

        if location and weather >= 15:
            # Suggest places
            places_info = places.get(location, {})
            return jsonify({
                "places": places_info, 
                "weather": weather
            })
        
        return jsonify({
            "error": "Location not found"}
        )

# Local foods endpoint
class LocalFoods(Resource):
    def get(self):
        location = request.args.get('location')
        foods = {
            "Paris": ["Baguette", "Tarte Tatin"],
            "Santiago": ["Churros", "Pisco Sake"]
        }[
            location or "default"
        ]
        return jsonify({
            "foods": foods
        })

# API
api.add_resource(TravelSuggest, '/suggest')
api.add_resource(LocalFoods, '/foods')

if __name__ == '__main__':
    app.run(debug=True)
