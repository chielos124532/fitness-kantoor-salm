import os
import csv
import sqlite3
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, send_file

app = Flask(__name__)

# Environment variables voor e-mail
GMAIL_SENDER = os.environ.get("GMAIL_SENDER")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")

def init_db():
    conn = sqlite3.connect('reserveringen.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reserveringen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            naam TEXT NOT NULL,
            datum TEXT NOT NULL,
            tijdslot TEXT NOT NULL,
            email TEXT
        )
    ''')
    conn.commit()
    conn.close()

def generate_tijdsloten():
    start = datetime.strptime("06:00", "%H:%M")
    end = datetime.strptime("22:00", "%H:%M")
    slots = []
    while start < end:
        slots.append(start.strftime("%H:%M"))
        start += timedelta(minutes=30)
    return slots

def send_confirmation_email(naam, datum, tijdslot, ontvanger_email):
    if not ontvanger_email:
        return

    start_dt = datetime.strptime(f"{datum} {tijdslot}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(hours=1)

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Fitness Reservering - Fitness Kantoor Salm
DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}
DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}
LOCATION:Fitness in het kantoor
DESCRIPTION:Je hebt een reservering van 1 uur gemaakt.
END:VEVENT
END:VCALENDAR
"""

    msg = EmailMessage()
    msg['Subject'] = 'Bevestiging reservering Fitness'
    msg['From'] = GMAIL_SENDER
    msg['To'] = ontvanger_email

    msg.set_content(
        f"Hallo {naam},\n\nJe hebt succesvol gereserveerd op {datum} om {tijdslot}.\n"
        f"Locatie: Fitness in het kantoor.\n\nGroet,\nFitness Kantoor Salm"
    )

    msg.add_attachment(ics_content.encode('utf-8'), maintype='text', subtype='calendar', filename='reservering.ics')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(GMAIL_SENDER, GMAIL_PASSWORD)
        smtp.send_message(msg)

@app.route('/', methods=['GET', 'POST'])
def reserveren():
    init_db()
    today = datetime.today().strftime('%Y-%m-%d')

    if request.method == 'POST':
        naam = request.form['naam']
        datum = request.form['datum']
        starttijd = request.form['tijdslot']
        email = request.form.get('email')

        start_dt = datetime.strptime(starttijd, "%H:%M")
        eindtijd = (start_dt + timedelta(minutes=30)).strftime("%H:%M")

        conn = sqlite3.connect('reserveringen.db')
        c = conn.cursor()

        c.execute('SELECT COUNT(*) FROM reserveringen WHERE datum=? AND tijdslot=?', (datum, starttijd))
        a1 = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM reserveringen WHERE datum=? AND tijdslot=?', (datum, eindtijd))
        a2 = c.fetchone()[0]

        if a1 < 4 and a2 < 4:
            c.execute('INSERT INTO reserveringen (naam, datum, tijdslot, email) VALUES (?, ?, ?, ?)', (naam, datum, starttijd, email))
            c.execute('INSERT INTO reserveringen (naam, datum, tijdslot, email) VALUES (?, ?, ?, ?)', (naam, datum, eindtijd, email))
            conn.commit()

            send_confirmation_email(naam, datum, starttijd, email)

            # Log naar CSV
            csv_bestand = 'reserveringen_log.csv'
            file_exists = os.path.isfile(csv_bestand)
            with open(csv_bestand, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['Datum', 'Starttijd', 'Naam', 'E-mailadres'])
                writer.writerow([datum, starttijd, naam, email or ''])

        conn.close()
        return redirect('/?success=1')

    tijdsloten = generate_tijdsloten()
    slots = []

    conn = sqlite3.connect('reserveringen.db')
    c = conn.cursor()
    for tijd in tijdsloten:
        c.execute('SELECT COUNT(*) FROM reserveringen WHERE datum=? AND tijdslot=?', (today, tijd))
        aantal = c.fetchone()[0]
        slots.append({'tijd': tijd, 'aantal': aantal})
    conn.close()

    return render_template('index.html', slots=slots, today=today)

@app.route('/admin')
def admin():
    conn = sqlite3.connect('reserveringen.db')
    c = conn.cursor()
    c.execute('SELECT naam, email, datum, tijdslot FROM reserveringen ORDER BY datum, tijdslot')
    rows = c.fetchall()
    conn.close()
    return render_template('admin.html', reserveringen=rows)

@app.route('/admin/download')
def download_csv():
    return send_file('reserveringen_log.csv', as_attachment=True)
