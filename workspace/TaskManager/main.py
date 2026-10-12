from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + str(Path(__file__).resolve().parent / "tasks.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@app.route("/")
def index():
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    return render_template("index.html", tasks=tasks)


@app.route("/add", methods=["POST"])
def add():
    description = request.form.get("description", "").strip()

    if description:
        task = Task(description=description)
        db.session.add(task)
        db.session.commit()

    return redirect(url_for("index"))


@app.route("/complete/<int:task_id>", methods=["POST"])
def complete(task_id):
    task = db.get_or_404(Task, task_id)
    task.completed = not task.completed
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>", methods=["POST"])
def delete(task_id):
    task = db.get_or_404(Task, task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for("index"))


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)