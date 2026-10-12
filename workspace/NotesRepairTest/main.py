from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///notes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from flask_sqlalchemy import SQLAlchemy

# Initialize database
db = SQLAlchemy(app)

# Model
class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, default=db.func.current_timestamp())

# Routes
@app.route('/')
def index():
    notes = Note.query.order_by(Note.date.desc()).all()
    return render_template('index.html', notes=notes)

@app.route('/add', methods=['POST'])
def add_note():
    content = request.form['content']
    new_note = Note(content=content)
    db.session.add(new_note)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_note(id):
    note = db.session.get(Note, id)
    if note:
        db.session.delete(note)
        db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)