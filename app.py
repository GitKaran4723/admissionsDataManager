from flask import Flask, request, render_template, redirect, session, url_for, jsonify
import pandas as pd
import requests
from threading import Thread
import time
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Global variable to store the DataFrame
data_df = pd.DataFrame()

def fetch_data():
    global data_df
    while True:
        try:
            url = os.getenv('AppScriptsURL')
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                df = pd.DataFrame(data)

                # Clean column names
                df.columns = [col.strip() for col in df.columns]

                # Cast critical fields to string
                df['Application'] = df['Application'].astype(str).str.strip()
                df['Phone Number'] = df['Phone Number'].astype(str).str.strip()

                data_df = df
        except Exception as e:
            print("Error fetching data:", e)
        time.sleep(60)  # Refresh every minute

# Background thread to fetch data
Thread(target=fetch_data, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/student-login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        app_num = request.form['application'].strip()
        phone = request.form['phone'].strip()
        student = data_df[(data_df['Application'] == app_num) & (data_df['Phone Number'] == phone)]
        if not student.empty:
            session['role'] = 'student'
            session['app_num'] = app_num
            return redirect('/student-dashboard')
        else:
            return "Invalid credentials"
    return render_template('student_login.html')

@app.route('/student-dashboard')
def student_dashboard():
    if 'role' in session and session['role'] == 'student':
        app_num = session['app_num']
        student_data = data_df[data_df['Application'] == app_num].to_dict('records')[0]
        return render_template('student_dashboard.html', student=student_data, is_teacher=False)
    return redirect('/')

@app.route('/teacher-login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == os.getenv('TEACHER_USERNAME') and password == os.getenv('TEACHER_PASSWORD'):
            session['role'] = 'teacher'
            return redirect('/teacher-dashboard')
        else:
            return "Invalid credentials"
    return render_template('teacher_login.html')

@app.route('/teacher-dashboard')
def teacher_dashboard():
    if 'role' in session and session['role'] == 'teacher':
        # Prepare student preview list
        student_preview = data_df[['Application', 'Candidate Name', 'Phone Number']].fillna('')

        # Seat statistics
        total_seats = 180
        filled_seats = data_df['Seat Category'].fillna('').astype(str).str.strip().replace('', pd.NA).dropna().shape[0]
        vacant_seats = total_seats - filled_seats

        # Sum up all installment columns
        installment_cols = [col for col in data_df.columns if 'Installment' in col]
        total_collected = data_df[installment_cols].apply(pd.to_numeric, errors='coerce').fillna(0).sum().sum()

        withdrawing_students = data_df[data_df['Joining'].str.upper().str.strip() == 'N'].shape[0]
        actual_strength = filled_seats - withdrawing_students

        return render_template(
            'teacher_dashboard.html',
            students=student_preview.to_dict('records'),
            total_seats=total_seats,
            filled_seats=filled_seats,
            vacant_seats=vacant_seats,
            withdrawing_students=withdrawing_students,
            actual_strength=actual_strength,
            total_collected=int(total_collected)
        )
    return redirect('/')


@app.route('/api/student/<app_id>')
def api_view_student(app_id):
    if 'role' in session and session['role'] == 'teacher':
        student = data_df[data_df['Application'] == app_id].to_dict('records')
        if student:
            return jsonify(student[0])
        return jsonify({'error': 'Student not found'}), 404
    return jsonify({'error': 'Unauthorized'}), 403

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
