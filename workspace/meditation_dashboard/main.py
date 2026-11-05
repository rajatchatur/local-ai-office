from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add', methods=['POST'])
def add():
    description = request.form['description']
    return redirect(url_for('index'))

@app.route('/delete', methods=['POST'])
def delete():
    return redirect(url_for('index'))

@app.route('/complete', methods=['POST'])
def complete():
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)