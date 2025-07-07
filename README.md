Personal Injury Law Chatbot
A smart chatbot for a personal injury law firm, built with Flask, Spacy, and SQLite. It scrapes real-time website content to answer queries about legal services (e.g., Slip & Fall, Motorcycle Accidents) and contact details. Features a responsive UI with a Quick Options palette that hides during user input and reappears after bot responses. Robust error handling ensures reliable content delivery.
Features

Dynamic Scraping: Fetches service and contact info using scraper.py.
**NLP Intentresearch: Powered by Spacy (nlp.py) for intent classification (services, contact, insurance, time limits).
Responsive UI: HTML/CSS (index.html, style.css) with smooth Quick Options transitions.
Backend: Flask (app.py) with SQLite (content.db) for caching and sessions.
Error Handling: Fixed scraper issues for consistent responses.

Prerequisites

Python 3.8+
ChromeDriver (matching your Chrome browser version)
Dependencies: flask, spacy, requests, beautifulsoup4, selenium, thefuzz

Setup Instructions

Clone the Repository:git clone <your-repo-url>
cd personal-injury-chatbot


Install Dependencies:pip install flask spacy requests beautifulsoup4 selenium thefuzz
python -m spacy download en_core_web_sm


Set Up ChromeDriver:
Download ChromeDriver from chromedriver.chromium.org matching your Chrome version.
Add ChromeDriver to your system PATH or place it in the project directory.


Run the Application:python app.py


Access the chatbot at http://localhost:5001.



Project Structure

app.py: Flask backend for handling requests.
nlp.py: NLP intent classification.
scraper.py: Scrapes website content.
templates/index.html: Frontend UI.
static/style.css: UI styling.
content.db: SQLite database for cached content.

How to Use

Open the chatbot by clicking the "Contact Us" button.
Type queries (e.g., “Do you handle slip and fall injuries?”) or select Quick Options (e.g., Motorcycle Accidents).
Receive responses with service details or contact info (e.g., phone, email).
The Quick Options palette hides during typing and reappears after the bot responds.

Testing

Test Queries:
“Slip Trip Fall”: Returns service details or fallback message.
“Contact Us”: Returns contact details (phone, email).


Check chatbot.log for errors.
Test on mobile to verify responsive design.

Troubleshooting

Scraper Issues: Ensure website URLs in scraper.py are accessible.
ChromeDriver Errors: Verify ChromeDriver version matches Chrome.
Dependencies: Run pip install -r requirements.txt if provided.

License
MIT License
