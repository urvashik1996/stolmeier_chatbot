import logging
from thefuzz import fuzz, process

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_keywords_and_intent(user_message, session_id, website_map, user_sessions):
    """Extract keywords and intent from user message with precise service matching."""
    logging.debug(f"Extracting keywords and intent from message: {user_message}")

    user_message_lower = user_message.lower().strip()
    keywords = []
    intent = None
    corrected_message = user_message_lower
    was_corrected = False

    # Define service titles exactly as they appear in website_map
    service_titles = {title.lower(): title for title in website_map.keys()}
    
    # Limited synonyms to avoid incorrect mappings
    synonyms = {
        'slip fall': 'slip trip fall',
        'slip and fall': 'slip trip fall',
        'dog bite': 'dog bites & attacks',
        'dog attack': 'dog bites & attacks',
        'product defect': 'product liability',
        'medical error': 'medical malpractice',
        'med mal': 'medical malpractice',
        'contact': 'contact us',
        'phone': 'contact us',
        'email': 'contact us',
        'address': 'contact us'
    }

    common_keywords = ['causes', 'cause', 'crash', 'proving liability', 
                       'contact info', 'phone', 'email', 'address', 'yes', 'no']

    # Step 1: Exact match for services
    if user_message_lower in service_titles:
        logging.debug(f"Exact match for service: {user_message_lower}")
        intent = 'service'
        keywords = [service_titles[user_message_lower]]
        return keywords, intent, corrected_message, was_corrected

    # Step 2: Exact match for specific subsections
    if user_message_lower == 'causes of car accidents':
        logging.debug(f"Exact match for 'causes of car accidents'")
        intent = 'subsection'
        keywords = ['causes', 'Car Accidents']
        return keywords, intent, corrected_message, was_corrected

    if user_message_lower in ['contact us', 'contact in email, address, phone no']:
        logging.debug(f"Exact match for 'contact us'")
        intent = 'contact'
        keywords = ['Contact Us']
        return keywords, intent, corrected_message, was_corrected

    # Step 3: Synonym match
    if user_message_lower in synonyms:
        corrected_message = synonyms[user_message_lower]
        was_corrected = True
        if corrected_message in service_titles:
            intent = "service"
            keywords = [service_titles[corrected_message]]
        else:
            intent = "contact"
            keywords = ['Contact Us']
        logging.debug(f"Synonym match: '{user_message_lower}' → '{corrected_message}'")
        return keywords, intent, corrected_message, was_corrected

    # Step 4: Fuzzy match with high threshold to avoid incorrect service mapping
    all_terms = list(service_titles.keys()) + list(synonyms.keys()) + common_keywords
    best_matches = process.extractBests(
        user_message_lower,
        all_terms,
        scorer=fuzz.token_set_ratio,
        score_cutoff=90,  # Slightly relaxed threshold for better matching
        limit=1
    )

    if best_matches:
        best_match, score = best_matches[0]
        if best_match in synonyms:
            corrected_message = synonyms[best_match]
            was_corrected = True
            if corrected_message in service_titles:
                intent = "service"
                keywords = [service_titles[corrected_message]]
            else:
                intent = "contact"
                keywords = ['Contact Us']
        elif best_match in service_titles:
            logging.debug(f"Fuzzy match: '{user_message_lower}' → '{best_match}' (score: {score})")
            corrected_message = best_match
            was_corrected = user_message_lower != best_match
            keywords = [service_titles[best_match]]
            intent = "service"
        elif best_match in ['contact info', 'phone', 'email', 'address']:
            intent = "contact"
            keywords = ['Contact Us']
            corrected_message = 'contact us'
            was_corrected = user_message_lower != 'contact us'
        else:
            intent = "general"
            keywords = [best_match]
        return keywords, intent, corrected_message, was_corrected

    # Step 5: Word-by-word analysis for general queries
    corrected_words = []
    for word in user_message_lower.split():
        if len(word) > 3:
            best_match, score = process.extractOne(word, all_terms, scorer=fuzz.partial_ratio)
            if score > 90 and best_match != word and word not in all_terms:
                corrected_words.append(best_match)
                was_corrected = True
                logging.debug(f"Corrected '{word}' to '{best_match}' (score: {score})")
            else:
                corrected_words.append(word)
        else:
            corrected_words.append(word)
    corrected_message = ' '.join(corrected_words)

    # Step 6: Intent detection for subsections or general queries
    if 'causes' in corrected_message and any(s in corrected_message for s in ['car accident', 'car accidents', 'crash']):
        intent = "subsection"
        keywords = ['causes', 'Car Accidents']
    elif any(title.lower() in corrected_message for title in service_titles.values()):
        intent = "service"
        matched_title = next(title for title in service_titles.values() if title.lower() in corrected_message)
        keywords = [matched_title]
    elif any(synonym in corrected_message for synonym in synonyms):
        intent = "service"
        matched_synonym = next(synonym for synonym in synonyms if synonym in corrected_message)
        keywords = [service_titles.get(synonyms[matched_synonym], synonyms[matched_synonym].capitalize())]
    elif 'proving liability' in corrected_message or 'prove liability' in corrected_message:
        intent = "subsection"
        keywords = ['proving liability']
    elif any(keyword in corrected_message for keyword in ['contact info', 'phone', 'email', 'address']):
        intent = "contact"
        keywords = ['Contact Us']
    elif corrected_message in ['yes', 'no']:
        intent = "feedback"
    else:
        intent = "general"
        for word in corrected_message.split():
            if word in service_titles or word in common_keywords or len(word) > 3:
                keywords.append(word)

    logging.debug(f"Final: Keywords={keywords}, Intent={intent}, Corrected={corrected_message}, Was_corrected={was_corrected}")
    return keywords, intent, corrected_message, was_corrected