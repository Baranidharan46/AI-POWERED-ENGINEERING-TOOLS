import streamlit as st
import google.generativeai as genai
import sqlite3
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configure Gemini API
API_KEY = "AIzaSyBCZebOrIz52leLLeUyXWpdJkDiBK9Vml0"
genai.configure(api_key=API_KEY)

# Initialize SQLite database
def init_db():
    try:
        conn = sqlite3.connect('submissions.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS contact_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        logger.debug("Database initialized.")
    except Exception as e:
        logger.error(f"DB init error: {e}")
        st.error(f"DB error: {e}")
    finally:
        conn.close()

init_db()

# HTTP server handler
class ContactHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/contact':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                name = data.get('name')
                email = data.get('email')
                message = data.get('message')

                if not all([name, email, message]):
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "All fields required"}).encode('utf-8'))
                    return

                conn = sqlite3.connect('submissions.db', check_same_thread=False)
                c = conn.cursor()
                c.execute('INSERT INTO contact_submissions (name, email, message) VALUES (?, ?, ?)',
                          (name, email, message))
                conn.commit()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"message": "Form submitted successfully!"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            finally:
                conn.close()
        else:
            self.send_response(404)
            self.end_headers()

# Start HTTP server
def run_server():
    try:
        server_address = ('localhost', 8000)
        httpd = HTTPServer(server_address, ContactHandler)
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"HTTP server error: {e}")

if 'server_started' not in st.session_state:
    st.session_state.server_started = True
    threading.Thread(target=run_server, daemon=True).start()

# Auth UI
st.sidebar.header("User Authentication")
auth_action = st.sidebar.radio("Select Action", ["Login", "Register"])

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

def register_user(username, email, password):
    try:
        conn = sqlite3.connect('submissions.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                  (username, email, password))
        conn.commit()
        return True, "Registration successful. Please log in."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def login_user(username, password):
    try:
        conn = sqlite3.connect('submissions.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        return user is not None
    except Exception as e:
        return False

if not st.session_state.logged_in:
    with st.sidebar:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if auth_action == "Register":
            email = st.text_input("Email")
            if st.button("Register"):
                success, msg = register_user(username, email, password)
                st.success(msg) if success else st.error(msg)
        elif st.button("Login"):
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success(f"Welcome {username}!")
            else:
                st.error("Invalid credentials")
else:
    st.sidebar.success(f"Logged in as {st.session_state.username}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""

# App UI
st.title("Prompt-Based Webpage Generator and Editor")

if "generated_html" not in st.session_state:
    st.session_state.generated_html = ""
if "edited_html" not in st.session_state:
    st.session_state.edited_html = ""

# Generate Webpage
st.subheader("Generate Webpage")
initial_prompt = st.text_area("Enter a prompt to generate a webpage:", value="""
Create a webpage for a bakery named 'Sweet Delights' with:
- Nav bar with Home, About, Menu, Contact, Login/Register
- Hero banner with heading and tagline
- Menu section with 3 items in grid
- About section with short text
- Contact form with JS POST to /api/contact
- Footer with copyright
- Inline CSS (white bg, pastel pink highlights)
- JS for form submission and responsive nav
- No external dependencies or images
""", height=250)

if st.button("Generate Webpage"):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(f"""
        Generate full HTML5 webpage from this prompt:
        '''{initial_prompt}'''
        Include inline CSS and JS, and return ONLY the HTML code.
        """)
        st.session_state.generated_html = response.text
        st.subheader("Generated HTML Code")
        st.code(response.text, language="html")
        st.subheader("Webpage Preview")
        st.components.v1.html(response.text, height=600, scrolling=True)
        st.download_button("Download HTML", data=response.text.encode('utf-8'), file_name="webpage.html")
    except Exception as e:
        st.error(f"Error: {e}")

# Edit Webpage
st.subheader("Edit Webpage")
edit_prompt = st.text_area("Edit instructions:", height=150)
if st.button("Edit Webpage") and st.session_state.generated_html:
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        edit_response = model.generate_content(f"""
        Take this HTML:
        ```{st.session_state.generated_html}```
        Edit it with:
        '''{edit_prompt}'''
        Return full HTML code only.
        """)
        st.session_state.edited_html = edit_response.text
        st.code(edit_response.text, language="html")
        st.components.v1.html(edit_response.text, height=600, scrolling=True)
        st.download_button("Download Edited HTML", data=edit_response.text.encode('utf-8'), file_name="edited.html")
    except Exception as e:
        st.error(f"Error: {e}")

# View Submissions
st.subheader("Contact Form Submissions")
try:
    conn = sqlite3.connect('submissions.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('SELECT id, name, email, message, submitted_at FROM contact_submissions')
    submissions = c.fetchall()
    for sub in submissions:
        st.write(f"ID: {sub[0]}, Name: {sub[1]}, Email: {sub[2]}, Message: {sub[3]}, Submitted: {sub[4]}")
    conn.close()
except Exception as e:
    st.error(f"Error fetching submissions: {e}")
