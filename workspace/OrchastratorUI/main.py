from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Dummy data
transactions = [
    {'transaction': 'TX001', 'enabled': True, 'updated': '2023-01-01'},
    {'transaction': 'TX002', 'enabled': False, 'updated': '2023-01-02'},
]

# Route to render the UI
@app.route('/')
def index():
    return render_template('index.html', transactions=transactions)

# Route to update transaction status
@app.route('/update', methods=['POST'])
def update():
    transaction = request.form['transaction']
    enabled = request.form['enabled'] == 'on'

    # Update the transaction in the database (mock)
    for i, t in enumerate(transactions):
        if t['transaction'] == transaction:
            transactions[i]['enabled'] = enabled
            transactions[i]['updated'] = request.form['updated']
            break

    return redirect(url_for('index'))

# Route to delete transaction
@app.route('/delete', methods=['POST'])
def delete():
    transaction = request.form['transaction']

    # Remove the transaction from the list
    for i, t in enumerate(transactions):
        if t['transaction'] == transaction:
            del transactions[i]
            break

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)