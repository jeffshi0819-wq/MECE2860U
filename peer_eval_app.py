import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import smtplib
import ssl
from email.message import EmailMessage
import random
import time

# --- CONFIGURATION ---
GOOGLE_SHEET_NAME = "MECE 2860U Results"
STUDENT_FILE = "students.csv"

# --- TEXT CONTENT ---
TITLE = "MECE 2860U Fluid Mechanics - Peer Review"
CONFIDENTIALITY_TEXT = """
**CONFIDENTIALITY:** This evaluation is a secret vote. 
**SUBMISSION DEADLINE:** One week after Lab 5.
"""

CRITERIA = ["Attendance at Meetings", "Meeting Deadlines", "Quality of Work", "Amount of Work", "Attitudes & Commitment"]

# --- CONNECTION ---
def get_google_sheet_connection():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        s_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(s_info, scopes=scopes)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Auth Error: {e}")
        return None

def save_to_google_sheets(current_user_id, new_rows):
    gc = get_google_sheet_connection()
    if not gc: return False
    try:
        sheet = gc.open(GOOGLE_SHEET_NAME).sheet1
        try:
            all_data = sheet.get_all_records()
            df = pd.DataFrame(all_data)
        except:
            df = pd.DataFrame()

        # Overwrite previous submission
        if not df.empty and 'Evaluator ID' in df.columns:
            df['Evaluator ID'] = df['Evaluator ID'].astype(str)
            df = df[df['Evaluator ID'] != str(current_user_id)]
        
        # Add new data
        final_df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        
        # Update Sheet
        sheet.clear()
        data = [final_df.columns.tolist()] + final_df.values.tolist()
        sheet.update(range_name='A1', values=data)
        return True
    except Exception as e:
        if "200" in str(e): return True # Ignore success code 200
        st.error(f"Save Error: {e}")
        return False

# --- EMAIL ---
def send_email(to_email, code):
    try:
        secrets = st.secrets["email"]
        msg = EmailMessage()
        msg.set_content(f"Your Code: {code}")
        msg["Subject"] = "Peer Eval Code"
        msg["From"] = secrets["sender_email"]
        msg["To"] = to_email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(secrets["smtp_server"], 465, context=context) as server:
            server.login(secrets["sender_email"], secrets["sender_password"])
            server.send_message(msg)
        return True
    except: return False

# --- APP UI ---
st.set_page_config(page_title="Peer Eval", layout="wide")
st.markdown("<style>.score-green {background-color:#28a745; color:white; padding:10px; border-radius:10px; text-align:center;} .score-red {background-color:#dc3545; color:white; padding:10px; border-radius:10px; text-align:center;}</style>", unsafe_allow_html=True)

if 'user' not in st.session_state: st.session_state['user'] = None
if 'otp' not in st.session_state: st.session_state['otp'] = None

try:
    df_students = pd.read_csv(STUDENT_FILE)
    df_students.columns = df_students.columns.str.strip()
    df_students['Student ID'] = df_students['Student ID'].astype(str)
except: st.stop()

if st.session_state['user'] is None:
    st.title(TITLE)
    name = st.selectbox("Select Name:", [""] + sorted(df_students['Student Name'].unique()))
    if st.button("Send Code") and name:
        user = df_students[df_students['Student Name'] == name].iloc[0]
        code = str(random.randint(1000,9999))
        st.session_state['otp'] = code
        st.session_state['temp'] = user.to_dict()
        if send_email(user['Email'], code): st.success("Code Sent")
        
    if st.button("Login") and st.text_input("Code") == st.session_state['otp']:
        st.session_state['user'] = st.session_state['temp']
        st.rerun()

else:
    u = st.session_state['user']
    st.title(TITLE)
    st.info(f"Welcome {u['Student Name']}")
    group = df_students[df_students['Group #'] == u['Group #']]
    data = []
    
    for _, peer in group.iterrows():
        st.subheader(f"Evaluating: {peer['Student Name']}")
        cols = st.columns(len(CRITERIA)+1)
        scores = [cols[i].number_input(c, 0, 100, 100, step=5, key=f"{peer['Student ID']}_{i}") for i, c in enumerate(CRITERIA)]
        avg = sum(scores)/len(scores)
        cols[-1].markdown(f"<div class='{'score-green' if avg>=80 else 'score-red'}'>{avg:.1f}%</div>", unsafe_allow_html=True)
        data.append({"Evaluator":u['Student Name'], "Evaluator ID":str(u['Student ID']), "Peer Name":peer['Student Name'], "Peer ID":str(peer['Student ID']), "Overall Score":avg, "Details":str(scores)})
        st.divider()

    if st.button("Submit") and save_to_google_sheets(u['Student ID'], data):
        st.balloons()
        st.success("Saved!")
