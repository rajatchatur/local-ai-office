from flask import Flask, jsonify,render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orchestrator.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'supersecretkey'

db = SQLAlchemy(app)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction = db.Column(db.String(100), nullable=False)
    enabled = db.Column(db.Boolean, default=False)
    updated = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'transaction': self.transaction,
            'enabled': self.enabled,
            'updated': self.updated.strftime('%Y-%m-%d %H:%M')
        }

@app.route('/', methods=['GET', 'POST'])
def index():
    transactions = Transaction.query.order_by(Transaction.updated.desc()).all()
    return render_template('index.html', transactions=transactions)

@app.route('/toggle/<int:transaction_id>', methods=['POST'])
def toggle_transaction(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    transaction.enabled = not transaction.enabled
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/create', methods=['POST'])
def create_transaction():
    transaction_name = request.form['transaction']
    new_transaction = Transaction(transaction=transaction_name, enabled=False)
    db.session.add(new_transaction)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    db.session.delete(transaction)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)