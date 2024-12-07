import logging

from flask import Flask, render_template, Response, jsonify, request
import cv2
import face_recognition
import numpy as np
import psycopg2
from datetime import datetime, timedelta

app = Flask(__name__)

# Database connection function
def get_db_connection():
    return psycopg2.connect(database="AiSystemDB", user="postgres", password="qwerty123", host="localhost", port="5432")

# Configure logging to write to a file
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger()
# logger = logging.getLogger('werkzeug')
# logger.setLevel(logging.ERROR)

# Load resident images and encodings from PostgreSQL
def load_resident_encodings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, image FROM residents_detail")
    rows = cursor.fetchall()
    conn.close()

    images = []
    ClassNames = []

    for row in rows:
        name, image_data = row
        ClassNames.append(name)
        
        # Convert binary data back to an image
        img_array = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        images.append(img)

    # Encode the images
    encode_list = []
    for img in images:
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(img_rgb)
        if encodings:
            encode_list.append(encodings[0])

    return encode_list, ClassNames

# Initialize encodings and class names
encodeListKnown, ClassNames = load_resident_encodings()
print("Encoding Complete")
logger.info("Encoding Complete")

# Function to mark attendance in the database
def mark_attendance(name):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now()
    date_today = now.date()
    #44
    current_time = now.strftime('%H:%M:%S')
    
    # Check if an entry exists for the resident today
    cursor.execute("SELECT * FROM entries WHERE name = %s AND date = %s", (name, date_today))
    entry = cursor.fetchone()

    if entry:
        entry_time, exit_time, re_entry, re_entry_time, status = entry[2], entry[3], entry[4], entry[5], entry[6]

        if status == "IN":
            check_time = re_entry_time if re_entry_time else entry_time
            time_diff = now - datetime.combine(date_today, check_time)
            if time_diff >= timedelta(minutes=10):
                cursor.execute(
                    "UPDATE entries SET exit_time = %s, status = 'OUT' WHERE name = %s AND date = %s",
                    (current_time, name, date_today)
                )
                print(f"Updated Exit_Time for {name} to {current_time} and status to OUT.")
                logger.info(f"Updated Exit_Time for {name} to {current_time} and status to OUT.")
            else:
                remaining_minutes = 10 - (time_diff.seconds // 60)
                print(f"Cannot update Exit_Time for {name}. {remaining_minutes} minutes remaining until allowed exit.")
                logger.info(f"Cannot update Exit_Time for {name}. {remaining_minutes} minutes remaining until allowed exit.")
        
        elif status == "OUT":
            if exit_time and (now - datetime.combine(date_today, exit_time)) >= timedelta(minutes=10):
                cursor.execute(
                    "UPDATE entries SET re_entry = TRUE, re_entry_time = %s, status = 'IN' WHERE name = %s AND date = %s",
                    (current_time, name, date_today)
                )
                print(f"Marked {name} as IN again (Re-Entry) with updated Re_Entry_Time to {current_time}.")
                logger.info(f"Marked {name} as IN again (Re-Entry) with updated Re_Entry_Time to {current_time}.")
            else:
                remaining_minutes = 10 - ((now - datetime.combine(date_today, exit_time)).seconds // 60) if exit_time else 10
                print(f"Cannot mark Re-Entry for {name}. {remaining_minutes} minutes remaining until allowed Re-Entry.")
                logger.info(f"Cannot mark Re-Entry for {name}. {remaining_minutes} minutes remaining until allowed Re-Entry.")
    else:
        # Insert new entry with all necessary columns if no record exists for today
        cursor.execute(
            """
            INSERT INTO entries (date, name, entry_time, exit_time, re_entry, re_entry_time, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (date_today, name, current_time, None, False, None, "IN")
        )
        print(f"Added new entry for {name}.")
        logger.info(f"Added new entry for {name}.")

    conn.commit()
    conn.close()

# Route to capture and serve the camera feed
def generate_frames():
    cap = cv2.VideoCapture(0)
    frame_skip = 10
    frame_count = 0
    
    while True:
        success, frame = cap.read()
        if not success:
            break

        # Process every nth frame
        frame_count += 1
        if frame_count % frame_skip == 0:
            imgS = cv2.resize(frame, (0, 0), None, 0.25, 0.25)
            imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)
            face_Current_Frame = face_recognition.face_locations(imgS)
            encoding_Current_Frame = face_recognition.face_encodings(imgS, face_Current_Frame)
            
            for encode_face, face_loc in zip(encoding_Current_Frame, face_Current_Frame):
                matches = face_recognition.compare_faces(encodeListKnown, encode_face)
                face_Distance = face_recognition.face_distance(encodeListKnown, encode_face)
                match_index = np.argmin(face_Distance)
                
                if matches[match_index]:
                    name = ClassNames[match_index].upper()
                    mark_attendance(name)
                    
                    y1, x2, y2, x1 = face_loc
                    y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.rectangle(frame, (x1, y2 - 35), (x2, y2), (0, 255, 0), cv2.FILLED)
                    cv2.putText(frame, name, (x1 + 6, y2 - 6), cv2.FONT_HERSHEY_COMPLEX, 0.8, (255, 255, 255), 2)
        
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Route to render the main page with attendance data from PostgreSQL
@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM entries")
    attendance_data = cursor.fetchall()
    conn.close()
    print("Attendance Data from DB:", attendance_data)
    logger.info("Attendance Data from DB:", attendance_data)
    return render_template('index.html', attendance_data=attendance_data)
    

@app.route('/add_resident', methods=['POST'])
def add_resident():
    try:
        name = request.form.get('name')
        address = request.form.get('address')
        block_no = request.form.get('block_no')
        resident_type = request.form.get('resident_type')
        image_file = request.files.get('image')

        if not all([name, address, block_no, resident_type, image_file]):
            return jsonify({'message': 'All fields are required'}), 400

        image_data = image_file.read()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO residents_detail (name, address, block_no, resident_type, image)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, address, block_no, resident_type, psycopg2.Binary(image_data)))
        conn.commit()
        conn.close()

        return jsonify({'message': f'Resident {name} added successfully'})
    except Exception as e:
        print(f"Error occurred: {e}")
        logger.info(f"Error occurred: {e}")
        return jsonify({'message': 'An error occurred while adding the resident'}), 500

@app.route('/fetch_attendance')
def fetch_attendance():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM entries ORDER BY date DESC, entry_time DESC")
    rows = cursor.fetchall()
    conn.close()

    attendance_data = [
        {
            'date': row[0].strftime('%Y-%m-%d'),
            'name': row[1],
            'entry_time': row[2].strftime('%H:%M:%S') if row[2] else None,
            'exit_time': row[3].strftime('%H:%M:%S') if row[3] else None,
            're_entry': row[4],
            're_entry_time': row[5].strftime('%H:%M:%S') if row[5] else None,
            'status': row[6]
        } for row in rows
    ]
    return jsonify(attendance_data)

@app.route('/fetch_logs')
def fetch_logs():
    try:
        with open('app.log', 'r') as log_file:
            # Read the last 20 lines (or adjust as needed)
            logs = log_file.readlines()[-20:]
        return jsonify(logs)
    except Exception as e:
        logger.info(f"Error fetching logs: {e}")
        return jsonify({'error': 'Failed to fetch logs'}), 500

if __name__ == "__main__":
    app.run(debug=True)
