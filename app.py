from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('reserveringen.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reserveringen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            naam TEXT NOT NULL,
            datum TEXT NOT NULL,
            tijdslot TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])  # <- route moet '/' zijn
def reserveren():
    init_db()
    if request.method == 'POST':
        naam = request.form['naam']
        datum = request.form['datum']
        tijdslot = request.form['tijdslot']

        # Check aantal reserveringen
        conn = sqlite3.connect('reserveringen.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM reserveringen WHERE datum=? AND tijdslot=?', (datum, tijdslot))
        aantal = c.fetchone()[0]
        if aantal < 5:  # max 5 mensen
            c.execute('INSERT INTO reserveringen (naam, datum, tijdslot) VALUES (?, ?, ?)', (naam, datum, tijdslot))
            conn.commit()
        conn.close()
        return redirect('/')

    # Toon reserveringen per slot
    today = datetime.today().strftime('%Y-%m-%d')
    tijdsloten = ['08:00', '09:00', '10:00', '11:00', '12:00']
    slots = []
    conn = sqlite3.connect('reserveringen.db')
    c = conn.cursor()
    for tijd in tijdsloten:
        c.execute('SELECT COUNT(*) FROM reserveringen WHERE datum=? AND tijdslot=?', (today, tijd))
        aantal = c.fetchone()[0]
        slots.append({'tijd': tijd, 'aantal': aantal})
    conn.close()
    return render_template('index.html', slots=slots, today=today)
