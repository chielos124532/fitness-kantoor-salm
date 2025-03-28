from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage

app = Flask(__name__)

# Vul deze in met je eigen Gmail info:
GMAIL_SENDER = "FitnessvanderSalm@gmail.com"
GMAIL_PASSWORD = "ycbvlqxnqjbteekr"

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

def generate_tijdsloten():
    start = datetime.strptime("06:00", "%H:%M")
    end = datetime.strptime("22:00", "%H:%M")
    slots = []
    while start < end:
        slots.append(start.strftime("%H:%M"))
        start += timedelta(minutes=30)
    return slots

def send_confirmation_email(naam, datum, tijdslot, ontvanger_email):
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

        # Check of beide blokken nog plek hebben
        c.execute('SELECT COUNT(*) FROM reserveringen WHERE datum=? AND tijdslot=?', (datum, starttijd))
        a1 = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM reserveringen WHERE datum=? AND tijdslot=?', (datum, eindtijd))
        a2 = c.fetchone()[0]

        if a1 < 4 and a2 < 4:
            c.execute('INSERT INTO reserveringen (naam, datum, tijdslot) VALUES (?, ?, ?)', (naam, datum, starttijd))
            c.execute('INSERT INTO reserveringen (naam, datum, tijdslot) VALUES (?, ?, ?)', (naam, datum, eindtijd))
            conn.commit()

            if email:
                send_confirmation_email(naam, datum, starttijd, email)

        conn.close()
        return redirect('/')

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
