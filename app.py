import os
import random
from itertools import product
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from werkzeug.utils import secure_filename
import sqlite3
import csv
import json
from io import StringIO, BytesIO
from PIL import Image, ImageDraw

app = Flask(__name__)
app.secret_key = 'secretkey'

UPLOAD_FOLDER = 'static/images'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DB_FILE = 'elephants.db'

colors = ["Red", "Orange", "Yellow", "Green", "Blue", "Purple"]
num_bars = 5
max_repeat = 3

def valid_sequence(seq, max_repeat):
    count = 1
    for i in range(1, len(seq)):
        if seq[i] == seq[i-1]:
            count += 1
            if count > max_repeat:
                return False
        else:
            count = 1
    return True

valid_codes = [combo for combo in product(colors, repeat=num_bars) if valid_sequence(combo, max_repeat)]

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize DB without AUTOINCREMENT
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS elephants (
    id INTEGER PRIMARY KEY,
    name TEXT,
    gender TEXT,
    origin TEXT,
    health TEXT,
    img TEXT,
    code TEXT
)
''')
conn.commit()
conn.close()

# -----------------------------
# Routes
@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')

        # Add / Save
        if action in ['add', 'save']:
            elephant_id = request.form.get('elephant_id')
            manual_id = request.form.get('manual_id')  # สำหรับ ID ที่กรอกเอง
            name = request.form.get('name')
            gender = request.form.get('gender')
            origin = request.form.get('origin')
            health = request.form.get('health')

            # Handle image upload
            img_file = request.files.get('img')
            img_path = ''
            if img_file and img_file.filename != '':
                filename = secure_filename(img_file.filename)
                img_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                img_file.save(img_path)

            if not name:
                flash('กรุณากรอกชื่อช้าง')
                return redirect(url_for('index'))

            if elephant_id:  # Update
                cursor.execute('''
                    UPDATE elephants
                    SET name=?, gender=?, origin=?, health=?, img=?
                    WHERE id=?
                ''', (name, gender, origin, health, img_path, elephant_id))
                flash('แก้ไขข้อมูลเรียบร้อย')
            else:  # Add
                # ตรวจสอบ manual_id
                if manual_id:
                    try:
                        manual_id = int(manual_id)
                        cursor.execute("SELECT id FROM elephants WHERE id=?", (manual_id,))
                        if cursor.fetchone():
                            flash(f'ID {manual_id} มีอยู่แล้ว กรุณาเลือก ID อื่น')
                            return redirect(url_for('index'))
                        new_id = manual_id
                    except ValueError:
                        flash('กรุณากรอก ID เป็นตัวเลข')
                        return redirect(url_for('index'))
                else:
                    # ใช้ ID ว่างต่ำสุด
                    cursor.execute("SELECT id FROM elephants ORDER BY id")
                    used_ids = [row['id'] for row in cursor.fetchall()]
                    new_id = 1
                    while new_id in used_ids:
                        new_id += 1

                selected_code = "-".join(random.choice(valid_codes))
                cursor.execute('''
                    INSERT INTO elephants (id, name, gender, origin, health, img, code)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (new_id, name, gender, origin, health, img_path, selected_code))
                flash(f'บันทึกข้อมูลเรียบร้อย (ID={new_id})')

            conn.commit()

        # Delete
        elif action == 'delete':
            elephant_id = request.form.get('elephant_id')
            if elephant_id:
                cursor.execute("DELETE FROM elephants WHERE id=?", (elephant_id,))
                conn.commit()
                flash('ลบข้อมูลเรียบร้อย')

        # Clear All
        elif action == 'clear':
            cursor.execute("DELETE FROM elephants")
            conn.commit()
            flash('ลบข้อมูลทั้งหมดเรียบร้อย')

        # Generate Random
        elif action == 'random':
            n = int(request.form.get('random_count', 3))
            sample_names = ["Chang Noi", "Chang Dum", "Chang Puak", "Chang Lek", "Chang Yai"]
            sample_gender = ["Male", "Female"]
            sample_origin = ["Chiang Mai", "Surin", "Kanchanaburi", "Ayutthaya"]
            sample_health = ["Healthy", "Injured", "Sick", "Recovering"]
            for _ in range(n):
                name = random.choice(sample_names)
                gender = random.choice(sample_gender)
                origin = random.choice(sample_origin)
                health = random.choice(sample_health)

                # Find lowest available ID
                cursor.execute("SELECT id FROM elephants ORDER BY id")
                used_ids = [row['id'] for row in cursor.fetchall()]
                new_id = 1
                while new_id in used_ids:
                    new_id += 1

                selected_code = "-".join(random.choice(valid_codes))
                cursor.execute('''
                    INSERT INTO elephants (id, name, gender, origin, health, img, code)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (new_id, name, gender, origin, health, '', selected_code))
            conn.commit()

        # Search
        elif action == 'search':
            keyword = request.form.get('search').strip().lower()
            elephants = cursor.execute("SELECT * FROM elephants").fetchall()
            found = None
            for e in elephants:
                if str(e['id']) == keyword or e['name'].lower() == keyword:
                    found = e
                    break
            if found:
                conn.close()
                return render_template('index.html', elephants=[found], form_data=found)
            else:
                flash('ไม่พบช้างที่ค้นหา')

        # Export CSV
        elif action == 'export_csv':
            cursor.execute("SELECT * FROM elephants")
            rows = cursor.fetchall()
            if rows:
                si = StringIO()
                writer = csv.writer(si)
                writer.writerow(["ID", "Name", "Gender", "Origin", "Health", "Image", "Code"])
                for row in rows:
                    writer.writerow([row['id'], row['name'], row['gender'], row['origin'], row['health'], row['img'], row['code']])
                output = BytesIO()
                output.write(si.getvalue().encode('utf-8'))
                output.seek(0)
                conn.close()
                return send_file(output, mimetype='text/csv', as_attachment=True, download_name='elephants.csv')
            else:
                flash('ไม่มีข้อมูลช้าง')

        # Export JSON
        elif action == 'export_json':
            cursor.execute("SELECT * FROM elephants")
            rows = cursor.fetchall()
            elephants = []
            for row in rows:
                elephants.append({
                    'id': row['id'],
                    'name': row['name'],
                    'gender': row['gender'],
                    'origin': row['origin'],
                    'health': row['health'],
                    'img': row['img'],
                    'code': row['code']
                })
            if elephants:
                conn.close()
                return app.response_class(json.dumps(elephants, ensure_ascii=False, indent=4),
                                          mimetype='application/json',
                                          headers={"Content-Disposition": "attachment;filename=elephants.json"})
            else:
                flash('ไม่มีข้อมูลช้าง')

    # Default GET
    elephants = cursor.execute("SELECT * FROM elephants").fetchall()
    conn.close()
    return render_template('index.html', elephants=elephants, form_data=None)

# -----------------------------
# Deploy-ready for Render
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
