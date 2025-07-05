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
from thefuzz import fuzz
from scraper import fetch_page, build_website_map, scrape_contact_info_fallback, scrape_targeted_content
from database import init_db, clear_database, get_content, store_content, get_contact_info, store_contact_info
from nlp import extract_keywords_and_intent

# Configure logging to file and console
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler('chatbot.log'),
    logging.StreamHandler()
])

sys.setrecursionlimit(2000)

app = Flask(__name__)

website_map = {}
user_sessions = {}
langchain_retriever = None
conversational_chain = None
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True, output_key="answer")
langchain_failed = False
MAIN_URL = "https://stolmeierlaw.com/"

# Define fallback_content globally
fallback_content = {
    'Car Accidents': "Stolmeier Law in San Antonio helps car accident victims seek compensation for injuries, medical expenses, and lost wages. Our experienced attorneys fight for your rights.",
    'Medical Malpractice': "Stolmeier Law assists victims of medical malpractice in San Antonio, seeking compensation for injuries caused by negligent healthcare providers.",
    'Slip Trip Fall': "Stolmeier Law represents clients in San Antonio injured in slip, trip, or fall accidents, helping them secure compensation for injuries and damages.",
    'Truck Accidents': "Stolmeier Law handles truck accident cases in San Antonio, fighting for compensation for injuries and damages caused by large vehicle collisions.",
    '18-Wheeler Accidents': "Stolmeier Law represents victims of 18-wheeler accidents in San Antonio, securing compensation for severe injuries and damages.",
    'Motorcycle Accidents': "Stolmeier Law supports motorcycle accident victims in San Antonio, seeking fair compensation for injuries and losses.",
    'Dog Bites & Attacks': "Stolmeier Law helps victims of dog bites and attacks in San Antonio recover compensation for medical costs and trauma.",
    'Product Liability': "Stolmeier Law handles product liability cases in San Antonio, fighting for those injured by defective products.",
    'Wrongful Death': "Stolmeier Law represents families in San Antonio for wrongful death claims, seeking justice and compensation.",
    'Recent Results': "Stolmeier Law has a strong track record of successful case outcomes in San Antonio. Contact us for details.",
    'About': "Stolmeier Law is a San Antonio-based firm specializing in personal injury cases, including car accidents, medical malpractice, and more. Our dedicated attorneys provide expert legal representation.",
    'Contact Us': "Address: 219 E. Craig Place, San Antonio, TX 78212. Phone: 210-227-3612. Email: chris@stolmeierlaw.com."
}

subsection_fallbacks = {
    'Car Accidents - Causes': "- Speeding\n- Impaired Driving\n- Drunk driving\n- Driving under the influence of narcotics\n- Sleep deprivation\n- Reckless Driving\n- Disregarding traffic signs and/or signals\n- Disregarding traffic lanes\n- Disregarding fellow motorists\n- Distracted Driving\n- Texting\n- Non-hands free phone calls\n- Eating\n- Changing the radio\n- Use of GPS",
    'Car Accidents - What to Do': "1. Stop after the accident\n2. Assess yourself and your surroundings\n3. Contact the police\n4. Take pictures and videos\n5. Gather and exchange information\n6. Seek medical attention\n7. Contact your insurance company\n8. Contact experienced car accident lawyers",
    'Car Accidents - Injuries': "- Strains and bruises\n- Lacerations\n- Ligament strains\n- Whiplash\n- Chest injuries\n- Burns\n- Broken bones\n- Neck injuries\n- Penetration injuries\n- Organ damage\n- Brain injuries\n- Loss of limb\n- Paralysis\n- Death",
    'Car Accidents - Uninsured Driver': "If the other driver is uninsured, you may still have a case. Stolmeier Law can explore options like uninsured motorist coverage. Contact us at 210-227-3612.",
    'Car Accidents - Claim Deadline': "In Texas, you generally have two years to file a car accident claim. Contact Stolmeier Law at 210-227-3612 to ensure timely filing.",
    'Car Accidents - Partial Fault': "You can file a claim even if partially at fault in Texas under comparative negligence rules. Stolmeier Law can help; call 210-227-3612.",
    'Medical and Injury - Lost Wages': "You may be eligible for compensation for lost wages due to injury. Stolmeier Law evaluates your case for free; contact us at 210-227-3612.",
    'Medical and Injury - Qualifying Injuries': "Personal injury claims cover injuries like fractures, spinal damage, and more. Stolmeier Law offers free consultations; call 210-227-3612.",
    'Medical and Injury - Doctor Visit': "Seeing a doctor documents your injuries, strengthening your claim. Contact Stolmeier Law at 210-227-3612 before proceeding.",
    'Legal Process - Need Lawyer': "A lawyer can maximize your claim’s success. Stolmeier Law offers free consultations and contingency fees; call 210-227-3612.",
    'Legal Process - Case Value': "Case value depends on damages, liability, and more. Stolmeier Law provides free evaluations; contact us at 210-227-3612.",
    'Legal Process - Case Duration': "Personal injury cases may take months to years. Stolmeier Law ensures efficient handling; call 210-227-3612.",
    'Legal Process - Filing Process': "Filing a claim involves gathering evidence and submitting legal documents. Stolmeier Law guides you; contact 210-227-3612.",
    'Legal Process - Court': "Most cases settle, but some go to court. Stolmeier Law prepares you fully; call 210-227-3612.",
    'Fees and Costs - Cost': "Stolmeier Law works on contingency; you pay only if we win. Contact us at 210-227-3612 for details.",
    'Fees and Costs - Free Consultation': "We offer free consultations to review your case. Call Stolmeier Law at 210-227-3612 to schedule.",
    'Fees and Costs - Contingency': "Our contingency fee means no upfront costs; we get paid when you do. Call 210-227-3612.",
    'Fees and Costs - Losing Case': "If you lose, you owe no legal fees with our contingency plan. Contact Stolmeier Law at 210-227-3612.",
    'Case Evaluation - Review': "Stolmeier Law offers free case reviews to assess your claim. Call 210-227-3612 to schedule.",
    'Case Evaluation - Strong Claim': "A strong claim has clear liability and documented damages. Contact Stolmeier Law at 210-227-3612 for a free evaluation.",
    'Case Evaluation - Documents': "Provide medical records, accident reports, and receipts. Stolmeier Law assists; call 210-227-3612.",
    'Specific Case Types - Slip and Fall': "We handle slip and fall cases, securing compensation for injuries. Call Stolmeier Law at 210-227-3612.",
    'Specific Case Types - Workplace Injury': "Workplace injury claims may involve workers’ comp or third-party liability. Contact Stolmeier Law at 210-227-3612.",
    'Specific Case Types - Motorcycle Accidents': "We represent motorcycle accident victims for compensation. Call Stolmeier Law at 210-227-3612.",
    'Specific Case Types - Dog Bite': "We handle dog bite claims for medical costs and damages. Contact Stolmeier Law at 210-227-3612.",
    'Availability and Location - Areas Served': "Stolmeier Law serves San Antonio and surrounding areas. Call 210-227-3612 for availability.",
    'Availability and Location - Speak Now': "Call 210-227-3612 to speak with a Stolmeier Law attorney promptly.",
    'Immediate Help - Lawyer Now': "Contact Stolmeier Law at 210-227-3612 for immediate attorney consultation.",
    'Immediate Help - Fastest Help': "The fastest way is to call Stolmeier Law at 210-227-3612 for urgent help.",
    'Immediate Help - Schedule Consultation': "Schedule a free consultation by calling Stolmeier Law at 210-227-3612."
}

def adjust_to_100_words(text, is_fallback=False, keyword=None):
    """Adjust text to 50-100 words, using concise fallback if needed."""
    words = text.split()
    if len(words) > 100:
        return ' '.join(words[:100])
    elif len(words) < 50 and is_fallback:
        return f"Our team will reach you soon regarding {keyword or 'your query'}. Contact Stolmeier Law at 210-227-3612 or chris@stolmeierlaw.com."
    elif len(words) < 50:
        padding = "Stolmeier Law provides expert legal services in San Antonio, specializing in personal injury cases. Contact us at 210-227-3612."
        padding_words = padding.split()
        words.extend(padding_words[:50 - len(words)])
        return ' '.join(words)
    return text

def format_list_response(content, content_type):
    """Format list-based content for causes, what to do, or injuries."""
    if content_type in ["causes", "injuries"] and "\n" in content:
        return f"Car accident {content_type}:\n{content}\nContact Stolmeier Law at 210-227-3612 for assistance."
    elif content_type == "what to do" and "\n" in content:
        return f"What to do after a car accident:\n{content}\nContact Stolmeier Law at 210-227-3612 for assistance."
    return content

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

        logging.debug("Loading documents for sections...")
        documents = []
        for section in target_sections:
            logging.debug(f"Processing section: {section}")
            content = get_content(section, 'description')
            if not content or content.startswith("Sorry,") or len(content.split()) < 30:
                logging.debug(f"No valid cached content for {section}, checking fallback...")
                content = fallback_content.get(section, f"{section} content placeholder.")
                section_url = website_map.get(section, {}).get('url', MAIN_URL)
                scraped_content = scrape_targeted_content([section], 'description', 'init_session', section_url, website_map)
                if scraped_content and not scraped_content.startswith("Sorry,") and "lorem ipsum" not in scraped_content.lower():
                    content = adjust_to_100_words(scraped_content)
                else:
                    content = adjust_to_100_words(fallback_content.get(section, f"{section} content placeholder."), is_fallback=True, keyword=section)
                store_content(section, section_url, 'description', content)

            if section == "Car Accidents":
                for subsection, sub_content in subsection_fallbacks.items():
                    if not get_content(subsection, subsection.split(' - ')[1].lower()):
                        store_content(subsection, MAIN_URL, subsection.split(' - ')[1].lower(), sub_content)
                for sub in ['Causes', 'What to Do', 'Injuries', 'Uninsured Driver', 'Claim Deadline', 'Partial Fault']:
                    logging.debug(f"Processing {sub} for Car Accidents")
                    subsection = sub.lower()
                    content_key = f"Car Accidents - {sub}"
                    sub_content = get_content(content_key, subsection)
                    if not sub_content or sub_content.startswith("Sorry,") or len(sub_content.strip()) < 10:
                        logging.debug(f"No valid cached {subsection} for Car Accidents, scraping...")
                        section_url = website_map.get(section, {}).get('url', MAIN_URL)
                        sub_content = scrape_targeted_content([subsection, section], subsection, 'init_session', section_url, website_map)
                        if sub_content and not sub_content.startswith("Sorry,"):
                            store_content(content_key, section_url, subsection, sub_content)
                        else:
                            sub_content = subsection_fallbacks.get(content_key, f"Our team will reach you soon regarding {subsection}. Contact 210-227-3612.")
                            store_content(content_key, section_url, subsection, sub_content)

            if section == "Contact Us":
                contact_content = get_content(section, 'contact')
                if not contact_content or contact_content.startswith("Sorry,") or len(contact_content.split()) < 10:
                    contact_content = scrape_contact_info_fallback()
                    store_content(section, MAIN_URL, 'contact', contact_content)
                    store_contact_info(contact_content)

            logging.debug(f"Creating temporary file for {section}")
            try:
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf8') as temp_file:
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
    """Render the main page."""
    try:
        logging.debug("Attempting to render index.html from D:\chatbot\templates")
        return render_template('index.html')
    except Exception as e:
        logging.error(f"Error rendering index.html: {str(e)}")
        return jsonify({'error': 'Template not found'}), 404

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
            content = "Our team will reach you soon. Contact Stolmeier Law at 210-227-3612 or chris@stolmeierlaw.com."
            return jsonify({'response': {'message': content}, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        generic_messages = ["help me", "hii", "hi", "hello", "hey"]
        if user_message.lower() in generic_messages:
            content = adjust_to_100_words("I can help with services like Car Accidents, Contact Us, or others. Please ask a specific question or select a service below.")
            memory.clear()
            return jsonify({'response': {'message': content}, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        service_titles = {title.lower(): title for title in website_map.keys()}
        keywords, intent, corrected_message, was_corrected = extract_keywords_and_intent(user_message, session_id, website_map, user_sessions)
        correction_note = f"<p class='correction-note'>Did you mean '{corrected_message}'?</p>" if was_corrected and corrected_message != user_message.lower() else ""

        logging.debug(f"Processing query: {user_message}, Intent: {intent}, Keywords: {keywords}")

        if intent == "accidents" or user_message.lower() in ["accidents", "accident", "accidents services"]:
            logging.debug("Handling accidents intent")
            content = adjust_to_100_words("Stolmeier Law handles various accident cases in San Antonio, including Car Accidents, Truck Accidents, and Motorcycle Accidents. Please specify a service for details.")
            response = {'message': correction_note + content if correction_note else content}
            return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        if intent == "contact" or user_message.lower() in [
            "contact us", "contact", "phone", "email", "address", "contact in email, address, phone no",
            "are you available in [city/state]", "what areas do you serve", "can i speak with someone now",
            "can i talk to a lawyer right now", "what’s the fastest way to get help", "how do i schedule a consultation",
            "where are you located", "what is your email", "how to reach you"
        ]:
            logging.debug("Contact intent detected")
            content = fallback_content['Contact Us']
            store_content("Contact Us", MAIN_URL, "contact", content)
            store_contact_info(content)
            response = {'message': correction_note + content if correction_note else content}
            return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        if intent == "feedback" or user_message.lower() in ["yes", "no"]:
            logging.debug(f"Feedback for session {session_id}: {user_message}")
            memory.clear()
            content = adjust_to_100_words("Thank you for your feedback! Ask about services like Car Accidents, Motorcycle Accidents, or Contact Us for more information.")
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
                        content = adjust_to_100_words(fallback_content.get(original_title, f"Our team will reach you soon regarding {original_title}. Contact 210-227-3612."), is_fallback=True, keyword=original_title)
                        store_content(original_title, section_url, 'description', content)
                else:
                    content = adjust_to_100_words(content)
                response = {'message': correction_note + content if correction_note else content}
                return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})
            except Exception as e:
                logging.error(f"Error processing service {original_title}: {str(e)}")
                content = adjust_to_100_words(fallback_content.get(original_title, f"Our team will reach you soon regarding {original_title}. Contact 210-227-3612."), is_fallback=True, keyword=original_title)
                response = {'message': correction_note + content if correction_note else content}
                return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        if intent == "subsection" and keywords:
            question_mappings = {
                'what to do after a car accident': ('Car Accidents', 'what to do'),
                'do i have a case if the other driver doesn’t have insurance': ('Car Accidents', 'uninsured driver'),
                'how long do i have to file a claim after a car accident': ('Car Accidents', 'claim deadline'),
                'can i still file a claim if i was partially at fault': ('Car Accidents', 'partial fault'),
                'i’m hurt and can’t work. can i get compensation for lost wages': ('Medical and Injury', 'lost wages'),
                'what kind of injuries qualify for a personal injury claim': ('Medical and Injury', 'qualifying injuries'),
                'do i need to see a doctor before contacting a lawyer': ('Medical and Injury', 'doctor visit'),
                'do i need a lawyer for a personal injury claim': ('Legal Process', 'need lawyer'),
                'how much is my case worth': ('Legal Process', 'case value'),
                'how long will my case take': ('Legal Process', 'case duration'),
                'what’s the process for filing a claim': ('Legal Process', 'filing process'),
                'will i have to go to court': ('Legal Process', 'court'),
                'how much does it cost to hire your firm': ('Fees and Costs', 'cost'),
                'do you offer free consultations': ('Fees and Costs', 'free consultation'),
                'do you work on a contingency fee basis': ('Fees and Costs', 'contingency'),
                'what happens if i lose my case': ('Fees and Costs', 'losing case'),
                'can someone review my case': ('Case Evaluation', 'review'),
                'how do i know if i have a strong claim': ('Case Evaluation', 'strong claim'),
                'what documents do i need to provide': ('Case Evaluation', 'documents'),
                'do you handle slip and fall injuries': ('Specific Case Types', 'slip and fall'),
                'can i sue for a workplace injury': ('Specific Case Types', 'workplace injury'),
                'do you take motorcycle accident cases': ('Specific Case Types', 'motorcycle accidents'),
                'can i file a claim for a dog bite': ('Specific Case Types', 'dog bite'),
                'are you available in [city/state]': ('Availability and Location', 'areas served'),
                'what areas do you serve': ('Availability and Location', 'areas served'),
                'can i speak with someone now': ('Availability and Location', 'speak now'),
                'can i talk to a lawyer right now': ('Immediate Help', 'lawyer now'),
                'what’s the fastest way to get help': ('Immediate Help', 'fastest help'),
                'how do i schedule a consultation': ('Immediate Help', 'schedule consultation')
            }
            user_message_lower = user_message.lower()
            matched_question = None
            for question, (section, subsection) in question_mappings.items():
                if fuzz.token_set_ratio(user_message_lower, question.lower()) > 90:
                    matched_question = (section, subsection)
                    break

            if matched_question:
                section, subsection = matched_question
                try:
                    section_url = website_map.get(section, {}).get('url', MAIN_URL)
                    content = get_content(f"{section} - {subsection.capitalize()}", subsection)
                    if not content or content.startswith("Sorry,") or len(content.strip()) < 5:
                        logging.debug(f"Scraping {subsection} for {section}")
                        content = scrape_targeted_content([subsection, section], subsection, session_id, section_url, website_map)
                        if content and not content.startswith("Sorry,") and "lorem ipsum" not in content.lower():
                            store_content(f"{section} - {subsection.capitalize()}", section_url, subsection, content)
                        else:
                            content = subsection_fallbacks.get(f"{section} - {subsection.capitalize()}", f"Our team will reach you soon regarding {subsection}. Contact 210-227-3612.")
                            store_content(f"{section} - {subsection.capitalize()}", section_url, subsection, content)
                    content = format_list_response(content, subsection)
                    response = {'message': correction_note + content if correction_note else content}
                    return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})
                except Exception as e:
                    logging.error(f"Error processing subsection query {section} - {subsection}: {str(e)}")
                    content = format_list_response(subsection_fallbacks.get(f"{section} - {subsection.capitalize()}", f"Our team will reach you soon regarding {subsection}. Contact 210-227-3612."), subsection)
                    response = {'message': correction_note + content if correction_note else content}
                    return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})
            else:
                matched_title = next((title for title in service_titles.values() if title.lower() in corrected_message.lower()), None)
                if not matched_title:
                    matched_title = "Car Accidents" if "accident" in corrected_message.lower() else "General"
                subsection_query = keywords[0].lower() if keywords else None
                try:
                    section_url = website_map.get(matched_title, {}).get('url', MAIN_URL)
                    content = get_content(f"{matched_title} - {subsection_query.capitalize()}", subsection_query)
                    if not content or content.startswith("Sorry,") or len(content.strip()) < 5:
                        logging.debug(f"Scraping {subsection_query} for {matched_title}")
                        content = scrape_targeted_content([subsection_query, matched_title], subsection_query, session_id, section_url, website_map)
                        if content and not content.startswith("Sorry,") and "lorem ipsum" not in content.lower():
                            store_content(f"{matched_title} - {subsection_query.capitalize()}", section_url, subsection_query, content)
                        else:
                            content = subsection_fallbacks.get(f"{matched_title} - {subsection_query.capitalize()}", f"Our team will reach you soon regarding {subsection_query}. Contact 210-227-3612.")
                            store_content(f"{matched_title} - {subsection_query.capitalize()}", section_url, subsection_query, content)
                    content = format_list_response(content, subsection_query)
                    response = {'message': correction_note + content if correction_note else content}
                    return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})
                except Exception as e:
                    logging.error(f"Error processing subsection query {matched_title} - {subsection_query}: {str(e)}")
                    content = format_list_response(subsection_fallbacks.get(f"{matched_title} - {subsection_query.capitalize()}", f"Our team will reach you soon regarding {subsection_query}. Contact 210-227-3612."), subsection_query)
                    response = {'message': correction_note + content if correction_note else content}
                    return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

        # Fallback for general queries
        try:
            logging.debug("Falling back to LangChain for general query")
            result = conversational_chain({"question": user_message})
            content = adjust_to_100_words(result["answer"], is_fallback=True, keyword=user_message)
            response = {'message': correction_note + content if correction_note else content}
            return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})
        except Exception as e:
            logging.error(f"Error with LangChain for general query: {str(e)}")
            content = adjust_to_100_words("Our team will reach you soon. Contact Stolmeier Law at 210-227-3612 or chris@stolmeierlaw.com.", is_fallback=True, keyword=user_message)
            response = {'message': correction_note + content if correction_note else content}
            return jsonify({'response': response, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

    except Exception as e:
        logging.error(f"Unexpected error in rag_query: {str(e)}\n{traceback.format_exc()}")
        content = "Our team will reach you soon. Contact Stolmeier Law at 210-227-3612 or chris@stolmeierlaw.com."
        return jsonify({'response': {'message': content}, 'helpful_prompt': 'Was this helpful? (Reply "yes" or "no")'})

if __name__ == '__main__':
    try:
        init_db()  # Initialize database
        app.run(debug=True, port=5001, use_reloader=False)
    except Exception as e:
        logging.error(f"Error running app: {str(e)}\n{traceback.format_exc()}")
        print(f"Error running app: {str(e)}")
        traceback.print_exc()