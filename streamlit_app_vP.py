# chat_app.py  
import streamlit as st
import sqlite3
import os
import json
import pandas as pd
import random
from datetime import datetime, date
#from streamlit_autorefresh import st_autorefresh
import warnings

# Ignore warnings
warnings.filterwarnings('ignore')

# Hide error details and stack traces from the app's UI
st.set_option('client.showErrorDetails', False)
#st.set_option('client.showErrorStackTrace', False)

# Constants
DB_PATH = 'data/chat_vP.db'
QUESTIONS_FILE = 'questions_list.xlsx'
MAPPING_FILE = 'data/date_questions_vP.json'
USER_A = 'User 1'
USER_B = 'User 2'

def init_db():
    """Initialize the SQLite database and create the messages table if it doesn't exist."""
    if not os.path.exists('data'):
        os.makedirs('data')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_connection():
    """Establish a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def send_message(sender, message, chat_date_str=None):
    """
    Insert a new message into the messages table.
    If chat_date_str is provided, use it as the timestamp (with time set to 00:00:00)
    so that the message is recorded for that specific day.
    """
    conn = get_connection()
    c = conn.cursor()
    if chat_date_str:
        timestamp_value = f"{chat_date_str} 00:00:00"
        c.execute("INSERT INTO messages (sender, message, timestamp) VALUES (?, ?, ?)",
                  (sender, message, timestamp_value))
    else:
        c.execute("INSERT INTO messages (sender, message) VALUES (?, ?)", (sender, message))
    conn.commit()
    conn.close()

def get_messages(selected_date=None):
    """
    Retrieve messages from the messages table.
    If selected_date is provided, filter messages for that specific date.
    """
    conn = get_connection()
    c = conn.cursor()
    if selected_date:
        # Filter messages by the selected date
        c.execute("""
            SELECT id, sender, message, timestamp 
            FROM messages 
            WHERE DATE(timestamp) = ?
            ORDER BY id ASC
        """, (selected_date,))
    else:
        # Retrieve all messages
        c.execute("""
            SELECT id, sender, message, timestamp 
            FROM messages 
            ORDER BY id ASC
        """)
    rows = c.fetchall()
    conn.close()
    return rows

def delete_message(message_id, username):
    """Delete a message by its ID if it was sent by the current user."""
    conn = get_connection()
    c = conn.cursor()
    # Verify that the message was sent by the current user
    c.execute("SELECT sender FROM messages WHERE id = ?", (message_id,))
    result = c.fetchone()
    if result and result[0] == username:
        c.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        conn.commit()
        conn.close()
        st.success("Message deleted successfully!")
    else:
        conn.close()
        st.error("You can only delete your own messages.")

def edit_message(message_id, username, new_message):
    """Update a message by its ID if it was sent by the current user."""
    conn = get_connection()
    c = conn.cursor()
    # Verify that the message was sent by the current user
    c.execute("SELECT sender FROM messages WHERE id = ?", (message_id,))
    result = c.fetchone()
    if result and result[0] == username:
        c.execute("UPDATE messages SET message = ? WHERE id = ?", (new_message, message_id))
        conn.commit()
        conn.close()
        st.success("Message updated successfully!")
    else:
        conn.close()
        st.error("You can only edit your own messages.")

def load_and_assign_questions():
    """
    Load questions from the Excel file, shuffle them, and assign one question per day.
    Save the mapping to a JSON file for persistence.
    """
    # Load all questions from all sheets
    try:
        xl = pd.ExcelFile(QUESTIONS_FILE)
        all_questions = []
        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            # Assuming questions are in the first column
            questions = df.iloc[:, 0].dropna().tolist()
            all_questions.extend(questions)
    except Exception as e:
        st.error(f"Error reading Excel file: {e}")
        return {}

    # Shuffle the questions
    random.shuffle(all_questions)

    # Assign one question per day
    mapping = {}
    days_in_year = 366 if is_leap_year(date.today().year) else 365
    for single_date in (date.today().replace(month=1, day=1) + pd.to_timedelta(n, unit='D') for n in range(days_in_year)):
        date_str = single_date.strftime("%Y-%m-%d")
        # Assign question by modulo to cycle if questions < days
        question = all_questions[(single_date.timetuple().tm_yday - 1) % len(all_questions)]
        mapping[date_str] = question

    # Save the mapping to a JSON file
    with open(MAPPING_FILE, 'w') as f:
        json.dump(mapping, f, indent=4)

    return mapping

def is_leap_year(year):
    """Check if a given year is a leap year."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def load_question_mapping():
    """
    Load the date-question mapping from the JSON file.
    If the file doesn't exist, create it.
    """
    if not os.path.exists('data'):
        os.makedirs('data')
    if not os.path.exists(MAPPING_FILE):
        st.info("Initializing date-question mapping...")
        mapping = load_and_assign_questions()
        if mapping:
            st.success("Date-question mapping initialized successfully!")
        else:
            st.error("Failed to initialize date-question mapping.")
        return mapping
    else:
        try:
            with open(MAPPING_FILE, 'r') as f:
                mapping = json.load(f)
            return mapping
        except Exception as e:
            st.error(f"Error loading date-question mapping: {e}")
            return {}

def main():
    # Initialize the database
    init_db()
    
    # Ensure editing state exists in session_state
    if "editing_message_id" not in st.session_state:
        st.session_state.editing_message_id = None
    
    # Set up Streamlit page configuration
    st.set_page_config(page_title="💬 Whysapp", page_icon="💬", layout="wide")
    
    # Auto-refresh setup: Refresh every 2 seconds, limit to 100 refreshes
    #st_autorefresh(interval=2000, limit=100, key="fizzbuzzcounter")
    
    # Load question mapping
    question_mapping = load_question_mapping()
    
    # Ensure "show_question_list" flag exists in session_state
    if "show_question_list" not in st.session_state:
        st.session_state.show_question_list = False

    # Display "Question list" button at the top right corner.
    top_right_cols = st.columns([9, 1])
    with top_right_cols[1]:
        if st.button("Question list", key="question_list_button"):
            st.session_state.show_question_list = True
            try:
                # Causes an error
                st.experimental_rerun()  # Rerun to update the UI with the selected user
            except Exception:
                pass  # Suppress the error
    
    # If the user has activated the Question list view, show the full-width table with a Back button.
    if st.session_state.show_question_list:
        # Filter out future dates and only include dates from 1 February 2025 up to today's date.
        today_str = date.today().strftime("%Y-%m-%d")
        filtered_items = [(d, q) for d, q in question_mapping.items() if "2025-02-01" <= d <= today_str]
        df_questions = pd.DataFrame(filtered_items, columns=["Date", "Daily Question"])
        st.dataframe(df_questions, use_container_width=True, hide_index=True)
        if st.button("Back", key="back_button"):
            st.session_state.show_question_list = False
            try:
                # Causes an error
                st.experimental_rerun()  # Rerun to update the UI with the selected user
            except Exception:
                pass  # Suppress the error
        return

    # User Login / Selection
    if 'username' not in st.session_state or st.session_state['username'] is None:
        st.header("Your profile")
        user = st.radio("Choose your identity:", (USER_A, USER_B))
        if st.button("Enter Chat"):
            st.session_state['username'] = user

        try:
            # Causes an error
            st.experimental_rerun()  # Rerun to update the UI with the selected user
        except Exception:
            pass  # Suppress the error
            
        return
    
    username = st.session_state['username']
    st.sidebar.header(f"Logged in as: {username}")
    if st.sidebar.button("Switch User"):
        st.session_state['username'] = None
        
        try:
            # Causes an error
            st.experimental_rerun()  # Rerun to update the UI with the selected user
        except Exception:
            pass  # Suppress the error
    
    # Date Selection for Viewing Chats
    st.subheader("📅 Select Date to View Our Chats")
    selected_date = st.date_input(
        "Choose a date",
        value=date.today(),
        min_value=date(2025, 2, 1),
        max_value=date.today()
    )
    selected_date_str = selected_date.strftime("%Y-%m-%d")
    
    # Get the question for the selected date
    daily_question = question_mapping.get(selected_date_str, "No question available for this date.")
    
    st.markdown(f"""
    <div>
        <h1 style='font-size: 35px; color: #A7FFFF;'>Question of the Day:</h1>
        <p style='font-size: 35px; color: #A7FFFF;'>{daily_question}\n</p>
    </div>
""", unsafe_allow_html=True)
    
    # Chat Display
    st.header("🗨️ Our Conversation")
    
    # Retrieve messages for the selected date
    messages = get_messages(selected_date=selected_date_str)
    
    if messages:
        for message in messages:
            msg_id, sender, content, timestamp = message
            timestamp_formatted = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
            if sender == username:
                # Messages sent by the current user
                # Use two columns: one for the message (and inline edit form) and one for the buttons.
                cols = st.columns([6, 4])
                with cols[0]:
                    # If this message is currently being edited, show an inline edit form.
                    if st.session_state.editing_message_id == msg_id:
                        new_text = st.text_input("Edit your message:", value=content, key=f"edit_input_{msg_id}")
                        if st.button("Submit Edit", key=f"submit_edit_{msg_id}"):
                            if new_text.strip() != "":
                                edit_message(msg_id, username, new_text.strip())
                                st.session_state.editing_message_id = None
                                try:
                                    st.experimental_rerun()  # Rerun to update the UI with the selected user
                                except Exception:
                                    pass  # Suppress the error
                    else:
                        st.markdown(f"""
                            <div style='text-align: left; background-color: #8E4700; padding: 10px; 
                                        border-radius: 10px; margin: 5px; display: inline-block; max-width: 100%;'>
                                <p style='font-size: 18px; margin: 0;'>You : {content}</p>
                            </div>
                        """, unsafe_allow_html=True)
                with cols[1]:
                    # Nest two columns to have Edit and Delete buttons immediately adjacent.
                    btn_cols = st.columns(2)
                    with btn_cols[0]:
                        if st.button("Edit", key=f"edit_{msg_id}"):
                            st.session_state.editing_message_id = msg_id
                            try:
                                st.experimental_rerun()  # Rerun to update the UI with the selected user
                            except Exception:
                                pass  # Suppress the error
                    with btn_cols[1]:
                        if st.button("Delete", key=f"delete_{msg_id}"):
                            delete_message(msg_id, username)
                            try:
                                st.experimental_rerun()  # Rerun to update the UI with the selected user
                            except Exception:
                                pass  # Suppress the error
            else:
                # Messages sent by the other user
                st.markdown(f"""
                    <div style='text-align: left; background-color: #4EA72E; padding: 10px; 
                                border-radius: 10px; margin: 5px; display: inline-block; max-width: 100%;'>
                        <p style='font-size: 18px; margin: 0;'>{sender} : {content}</p>
                    </div>
                """, unsafe_allow_html=True)
    
    else:
        st.info("No messages for the selected date.")
    
    # Input for new message   
    st.header("✉️ Send a message")
    with st.form(key='message_form', clear_on_submit=True):
        msg = st.text_input("Type your response here:", "")
        submit = st.form_submit_button("Send")
        if submit and msg.strip() != "":
            # If the selected date is not today's date, send the message with the selected date's timestamp.
            if selected_date_str != date.today().strftime("%Y-%m-%d"):
                send_message(username, msg.strip(), selected_date_str)
            else:
                send_message(username, msg.strip())
            st.success("Message sent!")

            try:
                st.experimental_rerun()  # Rerun to update the UI with the selected user
            except Exception:
                pass  # Suppress the error
            # Auto-refresh will handle updating the messages display
            

    # Button to clear all cache
    #if st.button("Clear Cache"):
        #st.cache_data.clear()      # Clears all data caches
        #st.cache_resource.clear()  # Clears all resource caches
        #st.success("Cache cleared!")

if __name__ == "__main__":
    main()
