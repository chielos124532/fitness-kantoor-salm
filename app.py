import os
import csv
import uuid
import sqlite3
import smtplib
from flask import Flask, render_template, request, redirect, session, send_file, url_for
from email.message import EmailMessage
from datetime import datetime, timedelta

app = Flask(__name__)

# Veilig via environment variables
GMAIL_SENDER = os.environ.get("GMAIL_SENDER")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")
ADMIN_CODE = os.environ.get("ADMIN_CODE", "geheim123")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supergeheimekey")

def init_db():
    conn = sqlite3.connect('reserveringen.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reserveringen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            naam TEXT NOT NULL,
            datum TEXT NOT NULL,
            tijdslot TEXT NOT NULL,
            email TEXT,
            annuleercode TEXT
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

def send_confirmation_email(naam, datum, tijdslot, ontvanger_email, annuleercode):
    if not ontvanger_email:
        return

    start_dt = datetime.strptime(f"{datum} {tijdslot}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(hours=1)
    link = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/mijn-reserveringen/{annuleercode}"

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Fitness Reservering - Fitness Kantoor Salm
DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}
DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}
LOCATION:Fitness in het kantoor
DESCRIPTION:Je hebt een reservering van 1 uur gemaakt.
END:VEVENT
END:VCALENDAR"""

    msg = EmailMessage()
    msg['Subject'] = 'Bevestiging reservering Fitness'
    msg['From'] = GMAIL_SENDER
    msg['To'] = ontvanger_email

    msg.set_content(
        f"Hallo {naam},\n\nJe hebt succesvol gereserveerd op {datum} om {tijdslot}.\n"
        f"Locatie: Fitness in het kantoor.\n\n"
        f"Wil je je reservering beheren of annuleren? Klik hier: {link}\n\nGroet,\nFitness Kantoor Salm"
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

        eindtijd = (datetime.strptime(starttijd, "%H:%M") + timedelta(minutes=30)).strftime("%H:%M")
        code = str(uuid.uuid4())  # unieke annuleercode

        conn = sqlite3.connect('reserveringen.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM reserveringen WHERE datum=? AND tijdslot=?', (datum, starttijd))
        a1 = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM reserveringen WHERE datum=? AND tijdslot=?', (datum, eindtijd))
        a2 = c.fetchone()[0]

        if a1 < 4 and a2 < 4:
            for tijd in [starttijd, eindtijd]:
                c.execute('INSERT INTO reserveringen (naam, datum, tijdslot, email, annuleercode) VALUES (?, ?, ?, ?, ?)',
                          (naam, datum, tijd, email, code))
            conn.commit()
            send_confirmation_email(naam, datum, starttijd, email, code)

            # Log naar CSV
            csv_bestand = 'reserveringen_log.csv'
            with open(csv_bestand, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if os.stat(csv_bestand).st_size == 0:
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

@app.route('/mijn-reserveringen/<code>', methods=['GET', 'POST'])
def mijn_reserveringen(code):
    conn = sqlite3.connect('reserveringen.db')
    c = conn.cursor()
    if request.method == 'POST':
        id_to_delete = request.form.get('delete_id')
        c.execute('DELETE FROM reserveringen WHERE id=? AND annuleercode=?', (id_to_delete, code))
        conn.commit()

    c.execute('SELECT id, datum, tijdslot FROM reserveringen WHERE annuleercode=? ORDER BY datum, tijdslot', (code,))
    rows = c.fetchall()
    conn.close()
    return render_template('mijn_reserveringen.html', reserveringen=rows, code=code)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        code = request.form.get('code')
        if code == ADMIN_CODE:
            session['admin'] = True
            return redirect(url_for('admin'))

    if not session.get('admin'):
        return render_template('admin_login.html')

    conn = sqlite3.connect('reserveringen.db')
    c = conn.cursor()
    c.execute('SELECT id, naam, email, datum, tijdslot FROM reserveringen ORDER BY datum, tijdslot')
    rows = c.fetchall()
    conn.close()
    return render_template('admin.html', reserveringen=rows)

@app.route('/admin/delete/<int:id>')
def delete(id):
    if not session.get('admin'):
        return redirect('/admin')

    conn = sqlite3.connect('reserveringen.db')
    c = conn.cursor()
    c.execute('DELETE FROM reserveringen WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/download')
def download_csv():
    if not session.get('admin'):
        return redirect('/admin')
    return send_file('reserveringen_log.csv', as_attachment=True)