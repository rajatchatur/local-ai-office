from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__) 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///recommendations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
api = Api(app)

# Database models

class Recommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type_ = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class TravelRecommendation(Resource):
    def get(self):
        recommendations = Recommendation.query.filter_by(type_='travel').all()
        return jsonify([
            {'type': r.type_, 'content': r.content, 'timestamp': r.timestamp.isoformat()} for r in recommendations
        ]) 

class FoodRecommendation(Resource):
    def get(self):
        recommendations = Recommendation.query.filter_by(type_='food').all()
        return jsonify([
            {'type': r.type_, 'content': r.content, 'timestamp': r.timestamp.isoformat()} for r in recommendations
        ]) 

class WeatherRecommendation(Resource):
    def get(self):
        recommendations = Recommendation.query.filter_by(type_='weather').all()
        return jsonify([
            {'type': r.type_, 'content': r.content, 'timestamp': r.timestamp.isoformat()} for r in recommendations
        ]) 

# Routes
@api.route('/recommendations', methods=['GET'])
def get_recommendations():
    recommendations = Recommendation.query.all()
    return jsonify([
        {'type': r.type_, 'content': r.content, 'timestamp': r.timestamp.isoformat()} for r in recommendations
    ]) 

if __name__ == '__main__':
    db.create_all()
    api.run(debug=True)

# Requirements.txt
# flask
# flask_restful
# flask-sqlalchemy