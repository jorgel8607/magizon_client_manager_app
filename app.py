from flask import Flask, render_template, request, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
import csv
from io import StringIO
import requests
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clients.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo de la base de datos
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True)

    def __repr__(self):
        return f"Client('{self.name}', '{self.email}', '{self.phone}')"

# Crear la base de datos
with app.app_context():
    db.create_all()

def suggest_correction(text):
    response = requests.post(
        'https://api.x.ai/v1/suggest',
        json={'text': text},
        headers={'Authorization': 'Bearer YOUR_API_KEY'}
    )
    return response.json().get('suggestions', [])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add', methods=['GET', 'POST'])
def add_client():
    suggestions = {}
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip() or None
        phone = request.form['phone'].strip() or None
        name_title = ' '.join(name.split()).title()
        # Sugerencias para nombre y email
        name_suggestions = suggest_correction(name)
        email_suggestions = suggest_correction(email) if email else []
        if name_suggestions:
            suggestions['name'] = name_suggestions
        if email_suggestions:
            suggestions['email'] = email_suggestions
        # Verificar si el cliente o email ya existen (case-insensitive)
        if Client.query.filter(db.func.lower(Client.name) == name_title.lower()).first():
            return render_template('add_client.html', message=f"Client '{name_title}' already exists.", suggestions=suggestions)
        if email and Client.query.filter(db.func.lower(Client.email) == email.lower()).first():
            return render_template('add_client.html', message=f"Email '{email}' already exists.", suggestions=suggestions)
        client = Client(name=name_title, email=email, phone=phone)
        db.session.add(client)
        db.session.commit()
        return render_template('add_client.html', message=f"Client '{name_title}' added.", suggestions=suggestions)
    return render_template('add_client.html', suggestions=suggestions)

@app.route('/edit/<int:client_id>', methods=['GET', 'POST'])
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip() or None
        phone = request.form['phone'].strip() or None
        name_title = ' '.join(name.split()).title()
        # Verificar si el nombre o email ya existen (excluyendo el cliente actual)
        existing_client = Client.query.filter(
            db.func.lower(Client.name) == name_title.lower(),
            Client.id != client_id
        ).first()
        if existing_client:
            return render_template('edit_client.html', client=client, message=f"Client '{name_title}' already exists.")
        if email and Client.query.filter(
            db.func.lower(Client.email) == email.lower(),
            Client.id != client_id
        ).first():
            return render_template('edit_client.html', client=client, message=f"Email '{email}' already exists.")
        client.name = name_title
        client.email = email
        client.phone = phone
        db.session.commit()
        return redirect(url_for('view_clients', message=f"Client '{name_title}' updated."))
    return render_template('edit_client.html', client=client)

@app.route('/remove/<int:client_id>')
def remove_client(client_id):
    client = Client.query.get(client_id)
    if client:
        db.session.delete(client)
        db.session.commit()
        return redirect(url_for('view_clients', message=f"Client '{client.name}' removed."))
    return redirect(url_for('view_clients', message="Client not found."))

@app.route('/view')
def view_clients():
    clients = Client.query.all()
    message = request.args.get('message')
    return render_template('view_clients.html', clients=clients, message=message)

@app.route('/search', methods=['GET', 'POST'])
def search_client():
    if request.method == 'POST':
        search_term = request.form['search_term'].strip().lower()
        clients = Client.query.filter(
            db.or_(
                Client.name.ilike(f'%{search_term}%'),
                Client.email.ilike(f'%{search_term}%'),
                Client.phone.ilike(f'%{search_term}%')
            )
        ).all()
        return render_template('view_clients.html', clients=clients)
    return render_template('search_client.html')

@app.route('/export')
def export_clients():
    clients = Client.query.all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Email', 'Phone'])
    for client in clients:
        writer.writerow([client.id, client.name, client.email or '', client.phone or ''])
    output.seek(0)
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=clients.csv'}
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)