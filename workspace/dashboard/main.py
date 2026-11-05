from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/tasks')
def tasks():
    return render_template('tasks.html')

@app.route('/tasks/<task_id>')
def task(task_id):
    return render_template('task.html', task_id=task_id)

@app.route('/tasks', methods=['POST'])
def add_task():
    task = request.form['task']
    return redirect(url_for('tasks'))

@app.route('/tasks/<task_id>', methods=['POST'])
def complete_task():
    return redirect(url_for('tasks'))

@app.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task():
    return redirect(url_for('tasks'))

if __name__ == '__main__':
    app.run(debug=True)