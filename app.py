import sys
import os
import logging
import tempfile
import time
import traceback
from flask import Flask, request, jsonify, render_template
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFacePipeline
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import Document
from scraper import fetch_page, build_website_map, scrape_contact_info_fallback, scrape_targeted_content
from nlp import extract_keywords_and_intent
from database import init_db, clear_database, get_content, store_content, get_contact_info, store_contact_info

# Increase recursion limit
sys.setrecursionlimit(2000)

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize global variables
website_map = {}
user_sessions = {}
langchain_retriever = None
conversational_chain = None
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True, output_key="answer")
langchain_failed = False
MAIN_URL = "https://stolmeierlaw.com/"

def adjust_to_100_words(text):
    """Adjust text to exactly 100 words, truncating or padding as needed."""
    words = text.split()
    if len(words) > 100:
        return ' '.join(words[:100])
    elif len(words) < 100:
        padding = "Stolmeier Law provides expert legal services in San Antonio, specializing in personal injury cases. For more details, visit our website or contact us."
        padding_words = padding.split()
        words.extend(padding_words[:100 - len(words)])
        return ' '.join(words)
    return text

def initialize_langchain():
    """Initialize LangChain with pre-defined content to avoid scraping delays."""
    global langchain_retriever, conversational_chain, langchain_failed
    logging.debug("Starting LangChain initialization...")
    try:
        target_sections = [
            'Car Accidents', 'Medical Malpractice', 'Slip Trip Fall', 'Truck Accidents',
            '18-Wheeler Accidents', 'Motorcycle Accidents', 'Dog Bites & Attacks',
            'Product Liability', 'Wrongful Death', 'Recent Results', 'About', 'Contact Us'
        ]
        fallback_content = {
            'Car Accidents': "Stolmeier Law in San Antonio helps car accident victims seek compensation for injuries, medical expenses, and lost wages. Our experienced attorneys fight for your rights.",
            'Medical Malpractice': "Stolmeier Law assists victims of medical malpractice in San Antonio, seeking compensation for injuries caused by negligent healthcare providers. Our attorneys fight for your rights.",
            'Slip Trip Fall': "Stolmeier Law represents clients in San Antonio injured in slip, trip, or fall accidents, helping them secure compensation for injuries and damages.",
            'About': "Stolmeier Law is a San Antonio-based firm specializing in personal injury cases, including car accidents, medical malpractice, and more. Our dedicated attorneys provide expert legal representation.",
            'Contact Us': "Address: 219 E. Craig Place, San Antonio, TX 78212. Phone: 210-227-3612. Email: chris@stolmeierlaw.com."
        }

        logging.debug("Loading documents for sections...")
        documents = []
        for section in target_sections:
            logging.debug(f"Processing section: {section}")
            content = get_content(section, 'description')
            if not content or content.startswith("Sorry,") or len(content.split()) < 30:
                logging.debug(f"No valid cached content for {section}, checking fallback...")
                content = fallback_content.get(section, f"{section} content placeholder.")
                if section in ['Car Accidents', 'Medical Malpractice', 'Slip Trip Fall', 'About', 'Contact Us']:
                    store_content(section, MAIN_URL, 'description', content)
                else:
                    section_url = website_map.get(section, {}).get('url', MAIN_URL)
                    scraped_content = scrape_targeted_content([section], 'description', 'init_session', section_url, website_map)
                    if scraped_content and not scraped_content.startswith("Sorry,") and "lorem ipsum" not in scraped_content.lower():
                        content = adjust_to_100_words(scraped_content)
                        store_content(section, section_url, 'description', content)
                    else:
                        content = adjust_to_100_words(fallback_content.get(section, f"{section} content placeholder."))
                        store_content(section, section_url, 'description', content)

            if section == "Car Accidents":
                logging.debug("Processing causes for Car Accidents")
                causes_content = get_content(f"{section} - Causes", 'causes')
                if not causes_content or causes_content.startswith("Sorry,") or len(causes_content.strip()) < 30:
                    logging.debug(f"No valid cached causes for {section}, scraping...")
                    section_url = website_map.get(section, {}).get('url', MAIN_URL)
                    causes_content = scrape_targeted_content([section], 'causes', 'init_session', section_url, website_map)
                    if causes_content and not causes_content.startswith("Sorry,"):
                        store_content(f"{section} - Causes", section_url, 'causes', causes_content)
                    else:
                        causes_content = "Common causes of car accidents include speeding, distracted driving, and impaired driving."
                        store_content(f"{section} - Causes", section_url, 'causes', causes_content)
                content += f"\nCauses of Car Accidents: {causes_content}"
                content = adjust_to_100_words(content)
                store_content(section, MAIN_URL, 'description', content)

            if section == "Contact Us":
                contact_content = get_content(section, 'contact')
                if not contact_content or contact_content.startswith("Sorry,") or len(contact_content.split()) < 10:
                    contact_content = scrape_contact_info_fallback()
                    store_content(section, MAIN_URL, 'contact', contact_content)
                    store_contact_info(contact_content)

            logging.debug(f"Creating temporary file for {section}")
            try:
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as temp_file:
                    temp_file.write(content)
                    temp_file_path = temp_file.name
            except Exception as e:
                logging.error(f"Error creating temp file for {section}: {str(e)}")
                continue

            try:
                logging.debug(f"Loading document from {temp_file_path}")
                loader = TextLoader(temp_file_path, encoding='utf-8')
                docs = loader.load()
                for doc in docs:
                    doc.metadata = {"page_title": section, "url": MAIN_URL}
                    documents.append(doc)
            except Exception as e:
                logging.error(f"Error loading document for {section}: {str(e)}")
            finally:
                try:
                    os.unlink(temp_file_path)
                    logging.debug(f"Deleted temp file: {temp_file_path}")
                except Exception as e:
                    logging.warning(f"Error deleting temp file {temp_file_path}: {str(e)}")

        if not documents:
            logging.error("No valid documents loaded. Aborting LangChain initialization.")
            langchain_failed = True
            return

        logging.debug(f"Loaded {len(documents)} documents")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50, length_function=len)
        split_docs = text_splitter.split_documents(documents)
        logging.debug(f"Split into {len(split_docs)} document chunks")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logging.debug("Initializing embeddings...")
                embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
                logging.debug("Initializing Chroma vector store...")
                persist_directory = os.path.join(os.getcwd(), "chroma_db")
                vector_store = Chroma.from_documents(
                    documents=split_docs,
                    embedding=embeddings,
                    persist_directory=persist_directory
                )
                logging.debug("Chroma vector store initialized successfully")
                break
            except Exception as e:
                logging.error(f"Attempt {attempt + 1}/{max_retries} - Error initializing Chroma: {str(e)}\n{traceback.format_exc()}")
                if attempt == max_retries - 1:
                    langchain_failed = True
                    return
                time.sleep(2)

        for attempt in range(max_retries):
            try:
                logging.debug("Initializing LLM...")
                llm = HuggingFacePipeline.from_model_id(
                    model_id="google/flan-t5-base",
                    task="text2text-generation",
                    pipeline_kwargs={"max_length": 1000}
                )
                logging.debug("LLM initialized successfully")
                break
            except Exception as e:
                logging.error(f"Attempt {attempt + 1}/{max_retries} - Error initializing LLM: {str(e)}")
                if attempt == max_retries - 1:
                    langchain_failed = True
                    return
                time.sleep(2)

        try:
            logging.debug("Setting up retriever and conversational chain...")
            langchain_retriever = vector_store.as_retriever(search_kwargs={"k": 2})
            conversational_chain = ConversationalRetrievalChain.from_llm(
                llm=llm,
                retriever=langchain_retriever,
                memory=memory,
                return_source_documents=True,
                output_key="answer"
            )
            logging.debug("LangChain initialization complete.")
            langchain_failed = False
        except Exception as e:
            logging.error(f"Error initializing conversational chain: {str(e)}")
            langchain_failed = True
            return
    except Exception as e:
        logging.error(f"Unexpected error in initialize_langchain: {str(e)}\n{traceback.format_exc()}")
        langchain_failed = True
        return

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/welcome', methods=['GET'])
def welcome():
    global website_map
    website_map = build_website_map()
    if not website_map:
        logging.error("Failed to build website map.")
        return jsonify({'message': 'Sorry, I couldn’t load the website sections.'})

    welcome_data = {
        'message': 'Welcome to Stolmeier Law! Ask about our services or select an option below.'
    }
    return jsonify(welcome_data)

@app.route('/rag_query', methods=['POST'])
def rag_query():
    """Handle user queries with strict prioritization and caching."""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        
        if not user_message:
            logging.error("No message received")
            return jsonify({'error': 'Please provide a question or select a service.'})

        global website_map, user_sessions, langchain_failed
        if not website_map:
            website_map = build_website_map()
            if not website_map:
                logging.error("Failed to build website map")
                return jsonify({'error': 'Unable to access the website.'})

        if langchain_failed or conversational_chain is None:
            logging.debug("Retrying LangChain initialization due to failure or None conversational_chain")
            initialize_langchain()
            if langchain_failed:
                logging.error("LangChain initialization failed after retry")
                return jsonify({'error': 'Sorry, I’m having trouble processing your request.'})

        if user_message.lower() == "no":
            logging.debug(f"User responded 'no' for session {session_id}")
            memory.clear()
            content = adjust_to_100_words("Our company assistant will contact you soon. For further assistance, please reach out to us.")
            return jsonify({'response': {'message': content}, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        generic_messages = ["help me", "hii", "hi", "hello", "hey"]
        if user_message.lower() in generic_messages:
            content = adjust_to_100_words("I can help with services like Car Accidents, Contact Us, or others. Please select a service from the options below.")
            memory.clear()
            return jsonify({'response': {'message': content}, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        service_titles = {title.lower(): title for title in website_map.keys()}
        keywords, intent, corrected_message, was_corrected = extract_keywords_and_intent(user_message, session_id, website_map, user_sessions)
        correction_note = f"<p class='correction-note'>Did you mean '{corrected_message}'?</p>" if was_corrected and corrected_message != user_message.lower() else ""

        logging.debug(f"Processing query: {user_message}, Intent: {intent}, Keywords: {keywords}")

        if intent == "accidents" or user_message.lower() in ["accidents", "accident", "accidents services"]:
            logging.debug("Handling accidents intent")
            content = adjust_to_100_words("Stolmeier Law handles various accident cases in San Antonio. For specific details on Car Accidents, Truck Accidents, or others, please select a service.")
            response = {'message': correction_note + content if correction_note else content}
            return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        if intent == "contact" or user_message.lower() in ["contact us", "contact", "contact in email, address, phone no"]:
            contact_text = get_content('Contact Us', 'contact') or get_contact_info()
            if not contact_text or contact_text.startswith("Sorry,") or len(contact_text.split()) < 10:
                logging.debug("Scraping contact information...")
                section_url = website_map.get('Contact Us', {}).get('url', MAIN_URL)
                contact_text = scrape_targeted_content(['Contact Us'], 'contact', session_id, section_url, website_map)
                if contact_text and not contact_text.startswith("Sorry,"):
                    contact_text = ' '.join(contact_text.split()[:50])
                    store_contact_info(contact_text)
                    store_content('Contact Us', section_url, 'contact', contact_text)
                else:
                    contact_text = scrape_contact_info_fallback()
                    store_contact_info(contact_text)
                    store_content('Contact Us', section_url, 'contact', contact_text)
            response = {'message': correction_note + contact_text if correction_note else contact_text}
            return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        if intent == "feedback":
            logging.debug(f"Feedback for session {session_id}: {user_message}")
            memory.clear()
            content = adjust_to_100_words("Thank you for your feedback! How can I assist you further? Please ask about our services like car accidents or contact information.")
            response = {'message': correction_note + content if correction_note else content}
            return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        if intent == "service" and keywords and keywords[0] in service_titles.values():
            original_title = keywords[0]
            try:
                section_url = website_map.get(original_title, {}).get('url', MAIN_URL)
                content = get_content(original_title, 'description')
                if not content or content.startswith("Sorry,") or len(content.split()) < 30:
                    logging.debug(f"Scraping description for {original_title}")
                    content = scrape_targeted_content([original_title], 'description', session_id, section_url, website_map)
                    if content and not content.startswith("Sorry,") and "lorem ipsum" not in content.lower():
                        content = adjust_to_100_words(content)
                        store_content(original_title, section_url, 'description', content)
                    else:
                        logging.warning(f"Scraping failed for {original_title}. Using fallback.")
                        fallback_content = {
                            'Car Accidents': "Stolmeier Law in San Antonio helps car accident victims seek compensation for injuries, medical expenses, and lost wages. Our experienced attorneys fight for your rights.",
                            'Medical Malpractice': "Stolmeier Law assists victims of medical malpractice in San Antonio, seeking compensation for injuries caused by negligent healthcare providers. Our attorneys fight for your rights.",
                            'Slip Trip Fall': "Stolmeier Law represents clients in San Antonio injured in slip, trip, or fall accidents, helping them secure compensation for injuries and damages.",
                            'About': "Stolmeier Law is a San Antonio-based firm specializing in personal injury cases, including car accidents, medical malpractice, and more. Our dedicated attorneys provide expert legal representation."
                        }
                        content = adjust_to_100_words(fallback_content.get(original_title, f"{original_title} content placeholder."))
                        store_content(original_title, section_url, 'description', content)
                else:
                    content = adjust_to_100_words(content)
                response = {'message': correction_note + content if correction_note else content}
                return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})
            except Exception as e:
                logging.error(f"Error processing service {original_title}: {str(e)}")
                content = adjust_to_100_words(f"Error fetching information for {original_title}. Please try again later.")
                response = {'message': correction_note + content if correction_note else content}
                return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        if intent == "subsection" and keywords and "car accidents" in [k.lower() for k in keywords] and "causes" in [k.lower() for k in keywords]:
            matched_title = "Car Accidents"
            try:
                section_url = website_map.get(matched_title, {}).get('url', MAIN_URL)
                content = get_content(f"{matched_title} - Causes", 'causes')
                if not content or content.startswith("Sorry,") or len(content.strip()) < 30:
                    logging.debug(f"Scraping causes for {matched_title}")
                    content = scrape_targeted_content([matched_title], 'causes', session_id, section_url, website_map)
                    if content and not content.startswith("Sorry,"):
                        store_content(f"{matched_title} - Causes", section_url, 'causes', content)
                    else:
                        content = adjust_to_100_words("Common causes of car accidents include speeding, distracted driving, and impaired driving. Contact Stolmeier Law for assistance.")
                        store_content(f"{matched_title} - Causes", section_url, 'causes', content)
                else:
                    causes_list = [cause.strip() for cause in content.split(';') if cause.strip()]
                    if not causes_list or causes_list == ['']:
                        causes_list = [content.strip()]
                    content = f"Causes of {matched_title}: {', '.join(causes_list)}"
                    content = adjust_to_100_words(content)
                response = {'message': correction_note + content if correction_note else content}
                return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})
            except Exception as e:
                logging.error(f"Error processing causes for {matched_title}: {str(e)}")
                content = adjust_to_100_words(f"Error fetching causes for {matched_title}. Please try again later.")
                response = {'message': correction_note + content if correction_note else content}
                return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        if intent == "subsection" and keywords:
            matched_title = next((title for title in service_titles.values() if title.lower() in corrected_message.lower()), "Car Accidents")
            subsection_query = keywords[0].lower() if keywords else None
            try:
                section_url = website_map.get(matched_title, {}).get('url', MAIN_URL)
                content = get_content(f"{matched_title} - {subsection_query}", subsection_query)
                if not content or content.startswith("Sorry,"):
                    content = scrape_targeted_content([matched_title], subsection_query, session_id, section_url, website_map)
                    if content and not content.startswith("Sorry,") and "lorem ipsum" not in content.lower():
                        content = adjust_to_100_words(content)
                        store_content(f"{matched_title} - {subsection_query}", section_url, subsection_query, content)
                    else:
                        content = adjust_to_100_words(f"Sorry, I couldn’t fetch information for {subsection_query} of {matched_title}. Please try again later.")
                else:
                    content = adjust_to_100_words(content)
                response = {'message': correction_note + content if correction_note else content}
                return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})
            except Exception as e:
                logging.error(f"Error processing subsection query {matched_title} - {subsection_query}: {str(e)}")
                content = adjust_to_100_words(f"Error fetching {subsection_query} for {matched_title}. Please try again later.")
                response = {'message': correction_note + content if correction_note else content}
                return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        logging.warning(f"Falling to general intent for query: {user_message}")
        try:
            section_url = MAIN_URL
            content = scrape_targeted_content(keywords, "general", session_id, section_url, website_map)
            if content and not content.startswith("Sorry,") and "lorem ipsum" not in content.lower():
                content = adjust_to_100_words(content)
            else:
                content = adjust_to_100_words(f"Sorry, I couldn’t fetch information for {user_message}. Please try again later.")
            response = {'message': correction_note + content if correction_note else content}
            return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})
        except Exception as e:
            logging.error(f"Error in general query '{user_message}': {str(e)}")
            memory.clear()
            content = adjust_to_100_words("Sorry, I couldn't understand your request. Could you provide more details.")
            return jsonify({'response': {'message': correction_note + content if correction_note else content}, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

    except Exception as e:
        logging.error(f"Unexpected error in rag_query: {str(e)}")
        content = adjust_to_100_words("An unexpected error occurred. Please try again or contact Stolmeier Law for assistance.")
        return jsonify({'error': correction_note + content if correction_note else content})

if __name__ == '__main__':
    clear_database()  # Clear stale data
    init_db()
    website_map = build_website_map()  # Initialize website map
    # Pre-populate database with fallback content
    fallback_content = {
        'Car Accidents': "Stolmeier Law in San Antonio helps car accident victims seek compensation for injuries, medical expenses, and lost wages. Our experienced attorneys fight for your rights.",
        'Medical Malpractice': "Stolmeier Law assists victims of medical malpractice in San Antonio, seeking compensation for injuries caused by negligent healthcare providers. Our attorneys fight for your rights.",
        'Slip Trip Fall': "Stolmeier Law represents clients in San Antonio injured in slip, trip, or fall accidents, helping them secure compensation for injuries and damages.",
        'About': "Stolmeier Law is a San Antonio-based firm specializing in personal injury cases, including car accidents, medical malpractice, and more. Our dedicated attorneys provide expert legal representation.",
        'Contact Us': "Address: 219 E. Craig Place, San Antonio, TX 78212. Phone: 210-227-3612. Email: chris@stolmeierlaw.com."
    }
    for section, content in fallback_content.items():
        store_content(section, MAIN_URL, 'description', content)
        if section == "Contact Us":
            store_content(section, MAIN_URL, 'contact', content)
            store_contact_info(content)
    store_content("Car Accidents - Causes", MAIN_URL, 'causes', "Common causes of car accidents include speeding, distracted driving, and impaired driving.")
    initialize_langchain()
    app.run(host='0.0.0.0', port=5000, debug=False)