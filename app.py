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

# Configure Gemini API with inline API key
API_KEY = "AIzaSyBCZebOrIz52leLLeUyXWpdJkDiBK9Vml0"
if not API_KEY or API_KEY == "your_api_key_here":
    st.error("Please replace 'your_api_key_here' with a valid Gemini API key from https://aistudio.google.com/app/apikey.")
else:
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
        conn.commit()
        logger.debug("SQLite database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        st.error(f"Database initialization failed: {str(e)}")
    finally:
        conn.close()

init_db()

# HTTP server to handle /api/contact
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

                logger.debug(f"Received POST data: {data}")

                if not all([name, email, message]):
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "All fields required"}).encode('utf-8'))
                    st.warning("Form submission failed: Missing fields.")
                    return

                conn = sqlite3.connect('submissions.db', check_same_thread=False)
                c = conn.cursor()
                c.execute('INSERT INTO contact_submissions (name, email, message) VALUES (?, ?, ?)',
                          (name, email, message))
                conn.commit()
                logger.debug(f"Stored submission: {name}, {email}, {message}")
                st.session_state.last_submission = f"Stored: Name={name}, Email={email}, Message={message}"

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"message": "Form submitted successfully!"}).encode('utf-8'))
            except Exception as e:
                logger.error(f"Error in POST handler: {str(e)}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                st.error(f"Form submission error: {str(e)}")
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
        logger.info("Starting HTTP server on http://localhost:8000")
        st.info("HTTP server started on http://localhost:8000")
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"HTTP server error: {str(e)}")
        st.error(f"Failed to start HTTP server: {str(e)}")

if 'server_started' not in st.session_state:
    st.session_state.server_started = True
    threading.Thread(target=run_server, daemon=True).start()

# Streamlit app title
st.title("Prompt-Based Webpage Generator and Editor")

# Session state
if "generated_html" not in st.session_state:
    st.session_state.generated_html = ""
if "edited_html" not in st.session_state:
    st.session_state.edited_html = ""
if "last_submission" not in st.session_state:
    st.session_state.last_submission = ""

# Step 1: Generate Webpage
st.subheader("Generate Webpage")
initial_prompt = st.text_area(
    "Enter a prompt to generate a webpage (default provided):",
    value="""
    Create a webpage for a bakery named "Sweet Delights" with a clear, semantic HTML5 structure and the following features:
    - A fixed navigation bar at the top with links to "Home", "About", "Menu", and "Contact" sections, using anchor tags (<a href="#section-id">) to navigate to sections within the page.
    - A Home section (<section id="home">) with a hero banner containing a heading ("Welcome to Sweet Delights") and a tagline ("Freshly baked goods daily").
    - A Menu section (<section id="menu">) displaying three baked goods (e.g., cupcakes, croissants, cakes) in a responsive grid layout using CSS grid.
    - An About section (<section id="about">) with a brief paragraph about the bakery’s history.
    - A Contact section with a form (name, email, message fields, and a submit button) that uses JavaScript to send data via a POST request to 'http://localhost:8000/api/contact'.
    - A footer (<footer>) with the text "© 2025 Sweet Delights" and placeholder social media links.
    - Use semantic HTML5 elements (e.g., <header>, <nav>, <section>, <footer>).
    - Apply a modern, responsive design with inline CSS in a <style> tag:
      - White background, pastel accents (e.g., light pink #FFB6C1 for buttons or hover effects).
      - Fixed navigation bar with a hamburger menu for mobile devices (collapsing at max-width: 600px).
      - Smooth scrolling for anchor links (e.g., scroll-behavior: smooth).
      - Hover effects on navigation links and form button.
    - Include inline JavaScript in a <script> tag to handle hamburger menu toggling and form submission to 'http://localhost:8000/api/contact'.
    - No external dependencies or images.
    """,
    height=250,
    key="initial_prompt"
)

if st.button("Generate Webpage"):
    if initial_prompt:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            full_prompt = f"""
            Generate HTML code for a webpage based on the following description: '{initial_prompt}'.
            The output should be a complete, valid HTML document with:
            - Proper HTML5 structure
            - Inline CSS in a <style> tag for a clean, modern, responsive design
            - Inline JavaScript in a <script> tag for form submission and navigation functionality
            - No external dependencies or images
            - Return only the HTML code, no explanations or comments
            """
            response = model.generate_content(full_prompt)
            st.session_state.generated_html = response.text
            st.session_state.edited_html = ""

            st.subheader("Generated HTML Code")
            st.code(st.session_state.generated_html, language="html")

            st.subheader("Preview of Generated Webpage")
            st.components.v1.html(st.session_state.generated_html, height=600, scrolling=True)

            st.subheader("Download Generated Webpage")
            st.download_button(
                label="Download Generated HTML",
                data=st.session_state.generated_html.encode('utf-8'),
                file_name="generated_webpage.html",
                mime="text/html"
            )
        except Exception as e:
            st.error(f"Error generating webpage: {str(e)}")
            logger.error(f"Generation error: {str(e)}")
    else:
        st.warning("Please enter a prompt.")

# Step 2: Edit Webpage
st.subheader("Edit Webpage")
edit_prompt = st.text_area(
    "Enter a prompt to edit the generated webpage:",
    height=150,
    key="edit_prompt"
)

if st.button("Edit Webpage"):
    if edit_prompt and st.session_state.generated_html:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            full_edit_prompt = f"""
            You are provided with the following HTML code:
            ```
            {st.session_state.generated_html}
            ```
            Modify the HTML code based on the following instructions: '{edit_prompt}'.
            Ensure the output is a complete, valid HTML document with:
            - Proper HTML5 structure
            - Inline CSS in a <style> tag
            - Inline JavaScript in a <script> tag, with form submission pointing to 'http://localhost:8000/api/contact'
            - No external dependencies or images
            - Return only the modified HTML code
            """
            response = model.generate_content(full_edit_prompt)
            st.session_state.edited_html = response.text

            st.subheader("Edited HTML Code")
            st.code(st.session_state.edited_html, language="html")

            st.subheader("Preview of Edited Webpage")
            st.components.v1.html(st.session_state.edited_html, height=600, scrolling=True)

            st.subheader("Download Edited Webpage")
            st.download_button(
                label="Download Edited HTML",
                data=st.session_state.edited_html.encode('utf-8'),
                file_name="edited_webpage.html",
                mime="text/html"
            )
        except Exception as e:
            st.error(f"Error editing webpage: {str(e)}")
            logger.error(f"Edit error: {str(e)}")
    else:
        st.warning("Please generate a webpage first or enter an edit prompt.")

# Test SQLite insert
st.subheader("Test SQLite Database")
if st.button("Insert Test Submission"):
    try:
        conn = sqlite3.connect('submissions.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT INTO contact_submissions (name, email, message) VALUES (?, ?, ?)',
                  ("Test User", "test@example.com", "Test Message"))
        conn.commit()
        st.success("Test submission inserted successfully.")
        logger.debug("Test submission inserted.")
    except Exception as e:
        st.error(f"Error inserting test submission: {str(e)}")
        logger.error(f"Test insert error: {str(e)}")
    finally:
        conn.close()

# Display stored submissions
st.subheader("View Contact Form Submissions")
if st.session_state.last_submission:
    st.write(f"Last Submission: {st.session_state.last_submission}")
try:
    conn = sqlite3.connect('submissions.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('SELECT id, name, email, message, submitted_at FROM contact_submissions')
    submissions = c.fetchall()
    conn.close()

    if submissions:
        for sub in submissions:
            st.write(f"ID: {sub[0]}, Name: {sub[1]}, Email: {sub[2]}, Message: {sub[3]}, Submitted: {sub[4]}")
    else:
        st.write("No submissions found.")
except Exception as e:
    st.error(f"Error fetching submissions: {str(e)}")
    logger.error(f"Fetch submissions error: {str(e)}")

# Instructions
st.markdown("""
### Instructions
1. Install required packages:
   ```
   pip install streamlit google-generativeai
   ```
2. Run the app:
   ```
   streamlit run app.py
   ```
3. The app runs an HTTP server on http://localhost:8000 for form submissions.
4. Generate a webpage, download it, and serve it via:
   ```
   python -m http.server 9000
   ```
5. Open http://localhost:9000/generated_webpage.html, submit the form, and check submissions here.
6. Use the "Insert Test Submission" button to verify SQLite functionality.
7. Check console logs for debugging.
""")