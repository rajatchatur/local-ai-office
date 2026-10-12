from flask import Flask, render_template, request, redirect, url_for

from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///notes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'Note({self.title})'

@app.route('/', methods=['GET', 'POST'])
def index():
    notes = Note.query.order_by(Note.id.desc()).all()
    return render_template('index.html', notes=notes)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'GET': 
        return render_template('add.html')
    else:
        new_note = Note(title=request.form['title'], content=request.form['content'])
        db.session.add(new_note)
        db.session.commit()
        return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    note = db.session.get(Note, id)
    if note:
        db.session.delete(note)
        db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__': 
    db.create_all()
    app.run(debug=True)