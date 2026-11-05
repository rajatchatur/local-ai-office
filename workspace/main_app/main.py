from flask import Flask, request, jsonify
from flask_restful import Resource, Api
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
api = Api(app)
CORS(app, resources=[{'path': '/'}])


class UserInstructions(Resource):
    def get(self):
        return jsonify({"instructions": "Please run the project by executing the following commands:\n\n1. Install dependencies: pip install -r requirements.txt\n2. Run the application: python main.py"})

class RunInstructions(Resource):
    def get(self):
        return jsonify({"instructions": "To run the project:\n\n1. Create a virtual environment and install dependencies: pip install -r requirements.txt\n2. Run the application: python main.py"})

if __name__ == '__main__':
    app.run(debug=True)


# Database models (not implemented in this minimal version)

# End of file