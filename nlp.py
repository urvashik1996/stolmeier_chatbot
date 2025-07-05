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

    service_titles = {title.lower(): title for title in website_map.keys()}
    
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
        'address': 'contact us',
        'crash': 'car accidents',
        'car crash': 'car accidents',
        'auto accident': 'car accidents',
        'attorney': 'contact us',
        'lawyer': 'contact us',
        'consultation': 'contact us',
        'free consultation': 'fees and costs',
        'contingency fee': 'fees and costs',
        'case worth': 'legal process',
        'case value': 'legal process',
        'case duration': 'legal process',
        'court case': 'legal process',
        'filing claim': 'legal process',
        'lost wages': 'medical and injury',
        'personal injury': 'medical and injury',
        'injury claim': 'medical and injury',
        'doctor visit': 'medical and injury',
        'case review': 'case evaluation',
        'strong claim': 'case evaluation',
        'claim documents': 'case evaluation',
        'workplace injury': 'specific case types',
        'motorcycle accident': 'specific case types',
        'areas served': 'availability and location',
        'speak now': 'availability and location',
        'lawyer now': 'immediate help',
        'fastest help': 'immediate help',
        'schedule consultation': 'immediate help',
        'causes': 'causes',
        'reasons': 'causes',
        'why accidents': 'causes',
        'what to do': 'what to do',
        'steps after': 'what to do',
        'post-accident': 'what to do',
        'after accident': 'what to do',
        'injury': 'injuries',
        'injuries': 'injuries',
        'hurt': 'injuries',
        'wounds': 'injuries',
        'insurance': 'uninsured driver',
        'uninsured': 'uninsured driver',
        'time limit': 'claim deadline',
        'deadline': 'claim deadline'
    }

    common_keywords = [
        'causes', 'cause', 'crash', 'proving liability', 'contact info', 'phone', 'email', 'address', 
        'yes', 'no', 'what to do', 'uninsured driver', 'claim deadline', 'partial fault', 
        'lost wages', 'qualifying injuries', 'doctor visit', 'need lawyer', 'case value', 
        'case duration', 'filing process', 'court', 'cost', 'free consultation', 'contingency', 
        'losing case', 'review', 'strong claim', 'documents', 'slip and fall', 
        'workplace injury', 'motorcycle accidents', 'dog bite', 'areas served', 
        'speak now', 'lawyer now', 'fastest help', 'schedule consultation', 'injuries',
        'insurance', 'uninsured', 'time limit', 'deadline'
    ]

    subsection_queries = {
        'causes of car accidents': ('subsection', ['causes', 'Car Accidents']),
        'what are the causes of car accidents': ('subsection', ['causes', 'Car Accidents']),
        'reasons for car accidents': ('subsection', ['causes', 'Car Accidents']),
        'why do car accidents happen': ('subsection', ['causes', 'Car Accidents']),
        'what to do after a car accident': ('subsection', ['what to do', 'Car Accidents']),
        'steps after a car accident': ('subsection', ['what to do', 'Car Accidents']),
        'what should i do after a car crash': ('subsection', ['what to do', 'Car Accidents']),
        'post-accident steps': ('subsection', ['what to do', 'Car Accidents']),
        'car accident injuries': ('subsection', ['injuries', 'Car Accidents']),
        'car accident injury': ('subsection', ['injuries', 'Car Accidents']),
        'injuries from car accidents': ('subsection', ['injuries', 'Car Accidents']),
        'what injuries from car accidents': ('subsection', ['injuries', 'Car Accidents']),
        'do i have a case if the other driver doesn’t have insurance': ('subsection', ['uninsured driver', 'Car Accidents']),
        'how long do i have to file a claim after a car accident': ('subsection', ['claim deadline', 'Car Accidents']),
        'can i still file a claim if i was partially at fault': ('subsection', ['partial fault', 'Car Accidents']),
        'i’m hurt and can’t work. can i get compensation for lost wages': ('subsection', ['lost wages', 'Medical and Injury']),
        'what kind of injuries qualify for a personal injury claim': ('subsection', ['qualifying injuries', 'Medical and Injury']),
        'do i need to see a doctor before contacting a lawyer': ('subsection', ['doctor visit', 'Medical and Injury']),
        'do i need a lawyer for a personal injury claim': ('subsection', ['need lawyer', 'Legal Process']),
        'how much is my case worth': ('subsection', ['case value', 'Legal Process']),
        'how long will my case take': ('subsection', ['case duration', 'Legal Process']),
        'what’s the process for filing a claim': ('subsection', ['filing process', 'Legal Process']),
        'will i have to go to court': ('subsection', ['court', 'Legal Process']),
        'how much does it cost to hire your firm': ('subsection', ['cost', 'Fees and Costs']),
        'do you offer free consultations': ('subsection', ['free consultation', 'Fees and Costs']),
        'do you work on a contingency fee basis': ('subsection', ['contingency', 'Fees and Costs']),
        'what happens if i lose my case': ('subsection', ['losing case', 'Fees and Costs']),
        'can someone review my case': ('subsection', ['review', 'Case Evaluation']),
        'how do i know if i have a strong claim': ('subsection', ['strong claim', 'Case Evaluation']),
        'what documents do i need to provide': ('subsection', ['documents', 'Case Evaluation']),
        'do you handle slip and fall injuries': ('subsection', ['slip and fall', 'Specific Case Types']),
        'can i sue for a workplace injury': ('subsection', ['workplace injury', 'Specific Case Types']),
        'do you take motorcycle accident cases': ('subsection', ['motorcycle accidents', 'Specific Case Types']),
        'can i file a claim for a dog bite': ('subsection', ['dog bite', 'Specific Case Types']),
        'are you available in [city/state]': ('contact', ['Contact Us']),
        'what areas do you serve': ('contact', ['Contact Us']),
        'can i speak with someone now': ('contact', ['Contact Us']),
        'can i talk to a lawyer right now': ('contact', ['Contact Us']),
        'what’s the fastest way to get help': ('contact', ['Contact Us']),
        'how do i schedule a consultation': ('contact', ['Contact Us']),
        'do i have a case if the other driver doesn’t have insurance': ('subsection', ['uninsured driver', 'Car Accidents']),
        'how long do i have to file a claim': ('subsection', ['claim deadline', 'Car Accidents'])
    }

    if user_message_lower in service_titles:
        logging.debug(f"Exact match for service: {user_message_lower}")
        intent = 'service'
        keywords = [service_titles[user_message_lower]]
        return keywords, intent, corrected_message, was_corrected

    for query, (query_intent, query_keywords) in subsection_queries.items():
        if fuzz.token_set_ratio(user_message_lower, query) > 90 or fuzz.partial_ratio(user_message_lower, query) > 90:
            logging.debug(f"Exact match for subsection query: {query}")
            return query_keywords, query_intent, query, user_message_lower != query

    if user_message_lower in synonyms:
        corrected_message = synonyms[user_message_lower]
        was_corrected = True
        if corrected_message in service_titles:
            intent = "service"
            keywords = [service_titles[corrected_message]]
        elif corrected_message in ['causes', 'what to do', 'injuries', 'uninsured driver', 'claim deadline']:
            intent = "subsection"
            keywords = [corrected_message, 'Car Accidents']
        else:
            intent = "contact"
            keywords = ['Contact Us']
        logging.debug(f"Synonym match: '{user_message_lower}' → '{corrected_message}'")
        return keywords, intent, corrected_message, was_corrected

    all_terms = list(service_titles.keys()) + list(synonyms.keys()) + common_keywords
    best_matches = process.extractBests(
        user_message_lower,
        all_terms,
        scorer=lambda x, y: max(fuzz.token_set_ratio(x, y), fuzz.partial_ratio(x, y)),
        score_cutoff=90,
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
            elif corrected_message in ['causes', 'what to do', 'injuries', 'uninsured driver', 'claim deadline']:
                intent = "subsection"
                keywords = [corrected_message, 'Car Accidents']
            else:
                intent = "contact"
                keywords = ['Contact Us']
        elif best_match in service_titles:
            logging.debug(f"Fuzzy match: '{user_message_lower}' → '{best_match}' (score: {score})")
            corrected_message = best_match
            was_corrected = user_message_lower != best_match
            keywords = [service_titles[best_match]]
            intent = "service"
        elif best_match in ['contact info', 'phone', 'email', 'address', 'areas served', 'speak now', 'lawyer now', 'fastest help', 'schedule consultation', 'insurance', 'uninsured', 'time limit', 'deadline']:
            intent = "contact" if best_match in ['contact info', 'phone', 'email', 'address', 'areas served', 'speak now', 'lawyer now', 'fastest help', 'schedule consultation'] else "subsection"
            keywords = ['Contact Us'] if intent == "contact" else [best_match, 'Car Accidents']
            corrected_message = 'contact us' if intent == "contact" else best_match
            was_corrected = user_message_lower != corrected_message
        else:
            intent = "subsection"
            keywords = [best_match]
        return keywords, intent, corrected_message, was_corrected

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

    for query, (query_intent, query_keywords) in subsection_queries.items():
        if any(keyword.lower() in corrected_message for keyword in query_keywords):
            intent = query_intent
            keywords = query_keywords
            break
    else:
        if 'causes' in corrected_message and any(s in corrected_message for s in ['car accident', 'car accidents', 'crash']):
            intent = "subsection"
            keywords = ['causes', 'Car Accidents']
            corrected_message = 'causes of car accidents'
            was_corrected = user_message_lower != corrected_message
        elif 'what to do' in corrected_message and any(s in corrected_message for s in ['car accident', 'car accidents', 'crash']):
            intent = "subsection"
            keywords = ['what to do', 'Car Accidents']
            corrected_message = 'what to do after a car accident'
            was_corrected = user_message_lower != corrected_message
        elif any(s in corrected_message for s in ['injury', 'injuries', 'hurt', 'wounds']) and any(s in corrected_message for s in ['car accident', 'car accidents', 'crash']):
            intent = "subsection"
            keywords = ['injuries', 'Car Accidents']
            corrected_message = 'car accident injuries'
            was_corrected = user_message_lower != corrected_message
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
        elif any(keyword in corrected_message for keyword in ['contact info', 'phone', 'email', 'address', 'areas served', 'speak now', 'lawyer now', 'fastest help', 'schedule consultation']):
            intent = "contact"
            keywords = ['Contact Us']
        elif any(keyword in corrected_message for keyword in ['insurance', 'uninsured', 'time limit', 'deadline']):
            intent = "subsection"
            keywords = ['uninsured driver' if 'insurance' in corrected_message or 'uninsured' in corrected_message else 'claim deadline', 'Car Accidents']
        elif corrected_message in ['yes', 'no']:
            intent = "feedback"
        else:
            intent = "general"
            keywords = [word for word in corrected_message.split() if word in service_titles or word in common_keywords or len(word) > 3]

    logging.debug(f"Final: Keywords={keywords}, Intent={intent}, Corrected={corrected_message}, Was_corrected={was_corrected}")
    return keywords, intent, corrected_message, was_corrected