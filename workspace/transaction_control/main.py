from flask import Flask, request, jsonify, render_template
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask import session

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///transactions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'supersecretkey'

db = SQLAlchemy(app)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction = db.Column(db.String(100), nullable=False)
    enabled = db.Column(db.Boolean, default=False)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'transaction': self.transaction,
            'enabled': self.enabled,
            'updated_date': self.updated_date.strftime('%Y-%m-%d %H:%M:%S')
        }

@app.route('/')
def index():
    transactions = Transaction.query.order_by(Transaction.updated_date.desc()).all()
    return render_template('index.html', transactions=transactions)

@app.route('/toggle/<int:id>', methods=['POST'])
def toggle_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    transaction.enabled = not transaction.enabled
    transaction.updated_date = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Transaction status updated'})

@app.route('/add', methods=['POST'])
def add_transaction():
    transaction = Transaction(
        transaction=request.form['transaction'],
        enabled=False
    )
    db.session.add(transaction)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Transaction added'})

@app.route('/delete/<int:id>', methods=['POST'])
def delete_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    db.session.delete(transaction)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Transaction deleted'})

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)

# templates/index.html
# <html>
# <head>
#     <title>Transaction Control</title>
# </head>
# <body>
#     <h1>Transaction Control</h1>
#     <form method="POST" action="/toggle/1">
#         <input type="text" name="transaction" placeholder="Transaction Name" required>
#         <button type="submit">Enable</button>
#     </form>
#     <form method="POST" action="/toggle/2">
#         <input type="text" name="transaction" placeholder="Transaction Name" required>
#         <button type="submit">Disable</button>
#     </form>
#     <form method="POST" action="/add">
#         <input type="text" name="transaction" placeholder="Transaction Name" required>
#         <button type="submit">Add</button>
#     </form>
#     <form method="POST" action="/delete/1">
#         <button type="submit">Delete</button>
#     </form>
# </body>
# </html>