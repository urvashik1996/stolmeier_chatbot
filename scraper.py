import requests
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_page(url):
    """Fetch page content from URL using requests."""
    try:
        response = requests.get(url, timeout=5)  # Reduced timeout for speed
        response.raise_for_status()
        return response.text
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def build_website_map(main_url="https://stolmeierlaw.com/"):
    """Build a website map using the main URL with DOM targeting."""
    logging.info(f"Building website map with main URL: {main_url}")
    website_map = {
        'Car Accidents': {'url': main_url, 'selector': 'div#car-accidents, section#car-accidents, article#car-accidents'},
        'Medical Malpractice': {'url': main_url, 'selector': 'div#medical-malpractice, section#medical-malpractice, article#medical-malpractice'},
        'Slip Trip Fall': {'url': main_url, 'selector': 'div#slip-trip-fall, section#slip-trip-fall, article#slip-trip-fall'},
        'Truck Accidents': {'url': main_url, 'selector': 'div#truck-accidents, section#truck-accidents, article#truck-accidents'},
        '18-Wheeler Accidents': {'url': main_url, 'selector': 'div#18-wheeler-accidents, section#18-wheeler-accidents, article#18-wheeler-accidents'},
        'Motorcycle Accidents': {'url': main_url, 'selector': 'div#motorcycle-accidents, section#motorcycle-accidents, article#motorcycle-accidents'},
        'Dog Bites & Attacks': {'url': main_url, 'selector': 'div#dog-bites-attacks, section#dog-bites-attacks, article#dog-bites-attacks'},
        'Product Liability': {'url': main_url, 'selector': 'div#product-liability, section#product-liability, article#product-liability'},
        'Wrongful Death': {'url': main_url, 'selector': 'div#wrongful-death, section#wrongful-death, article#wrongful-death'},
        'Recent Results': {'url': main_url, 'selector': 'div#recent-results, section#recent-results, article#recent-results'},
        'About': {'url': main_url, 'selector': 'div#about, section#about, article#about'},
        'Contact Us': {'url': main_url, 'selector': 'div#contact-us, section#contact-us, article#contact-us, address'}
    }
    return website_map

def scrape_contact_info_fallback():
    """Fallback for contact information."""
    return "Address: 219 E. Craig Place, San Antonio, TX 78212. Phone: 210-227-3612. Email: chris@stolmeierlaw.com."

def scrape_targeted_content(keywords, content_type, session_id, url, website_map=None):
    """Scrape targeted content from the provided URL with strict keyword filtering."""
    logging.info(f"Scraping: keywords={keywords}, content_type={content_type}, url={url}")

    if not url:
        url = "https://stolmeierlaw.com/"
        logging.warning(f"No URL provided, using main URL: {url}")

    try:
        html_content = fetch_page(url)
        if not html_content:
            logging.error(f"Failed to fetch content from {url}")
            return scrape_contact_info_fallback() if content_type == "contact" else f"Sorry, I couldn’t fetch the content for {keywords[0]}."

        soup = BeautifulSoup(html_content, 'html.parser')
        logging.debug(f"Parsed HTML content: {soup.get_text(separator=' ', strip=True)[:200]}...")

        # Remove navigation, footer, and irrelevant elements
        irrelevant_phrases = [
            'stolmeier law let this family fight for you', 'menu', 'home',
            'your name', 'your email', 'phone number', 'company', 'your message',
            'lorem ipsum', 'texas personal injury lawyers', 'call stolmeier law',
            'a stolmeier will always represent you', 'free consultation', 'contact us for any questions'
        ]
        for element in soup.find_all(['nav', 'footer', 'div', 'ul', 'ol', 'header', 'section', 'a', 'span'], class_=[
            'menu', 'dropdown-menu', 'footer', 'sidebar', 'widget', 'related-posts', 'navbar', 'nav', 'top-bar',
            'menu-item', 'nav-link', 'banner', 'slogan', 'contact-form'
        ]):
            element.decompose()
        for element in soup.find_all(['script', 'style', 'form', 'iframe']):
            element.decompose()
        for element in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'span', 'a']):
            text = element.get_text(separator=' ', strip=True).lower()
            if any(phrase in text for phrase in irrelevant_phrases):
                element.decompose()

        # Use selector from website_map if available
        selector = website_map.get(keywords[0], {}).get('selector', None) if website_map and keywords else None

        if content_type == "causes" and "Car Accidents" in keywords:
            causes = []
            relevant_causes = [
                'speeding', 'impaired driving', 'drunk driving', 'distracted driving', 'texting',
                'reckless driving', 'sleep deprivation', 'disregarding traffic signs', 'eating',
                'changing the radio', 'use of gps', 'disregarding traffic lanes', 'disregarding fellow motorists'
            ]
            target_elements = soup.select(selector) if selector else soup.find_all(['h2', 'h3', 'p', 'ul', 'section'])
            for section in target_elements:
                if not section:
                    continue
                section_text = section.get_text(separator=' ', strip=True).lower()
                if any(phrase in section_text for phrase in irrelevant_phrases):
                    continue
                if any(keyword.lower() in section_text for keyword in ['car accident', 'crash', 'causes']):
                    if section.name == 'ul' and section.find_all('li'):
                        li_texts = [li.get_text(separator=' ', strip=True) for li in section.find_all('li')]
                        causes.extend([text for text in li_texts if any(cause in text.lower() for cause in relevant_causes)])
                    elif any(cause in section_text for cause in relevant_causes):
                        causes.append(section.get_text(separator=' ', strip=True))
            causes = list(set(causes))  # Remove duplicates
            if causes:
                logging.info(f"Scraped causes: {causes[:3]}...")
                return "; ".join(causes)
            logging.warning(f"No causes found on {url} for Car Accidents")
            return "Common causes of car accidents include speeding, distracted driving, and impaired driving. Contact Stolmeier Law for assistance."

        elif content_type == "description":
            text = ""
            target_elements = soup.select(selector) if selector else soup.find_all(['p', 'div', 'article', 'h2', 'h3', 'section'])
            for section in target_elements:
                section_text = section.get_text(separator=' ', strip=True).lower()
                if any(phrase in section_text for phrase in irrelevant_phrases):
                    continue
                if any(keyword.lower() in section_text for keyword in keywords):
                    text += section.get_text(separator=' ', strip=True) + " "
                    if len(text.split()) >= 30:
                        break
            text = ' '.join(text.split()).strip()
            word_count = len(text.split())
            if word_count >= 30:
                return text
            logging.warning(f"Description for {keywords} has only {word_count} words")
            if "car accidents" in [k.lower() for k in keywords]:
                return "Stolmeier Law in San Antonio helps car accident victims seek compensation for injuries, medical expenses, and lost wages. Our experienced attorneys fight for your rights."
            elif "medical malpractice" in [k.lower() for k in keywords]:
                return "Stolmeier Law assists victims of medical malpractice in San Antonio, seeking compensation for injuries caused by negligent healthcare providers. Our attorneys fight for your rights."
            elif "about" in [k.lower() for k in keywords]:
                return "Stolmeier Law is a San Antonio-based firm specializing in personal injury cases, including car accidents, medical malpractice, and more. Our dedicated attorneys provide expert legal representation."
            elif "slip trip fall" in [k.lower() for k in keywords]:
                return "Stolmeier Law represents clients in San Antonio injured in slip, trip, or fall accidents, helping them secure compensation for injuries and damages. Contact us for expert legal support."
            return f"{keywords[0]} content placeholder."

        elif content_type == "contact":
            contact_text = ""
            target_elements = soup.select(selector) if selector else soup.find_all(['p', 'div', 'a', 'h3', 'address', 'span'])
            for element in target_elements:
                text = element.get_text(separator=' ', strip=True).lower()
                if any(phrase in text for phrase in irrelevant_phrases):
                    continue
                if any(keyword in text for keyword in ['address', 'phone', 'email', 'contact', 'san antonio', 'tx']):
                    contact_text += element.get_text(separator=' ', strip=True) + " "
            contact_text = ' '.join(contact_text.split()[:50])
            if len(contact_text.split()) >= 10:
                return contact_text
            logging.warning(f"Contact text too short: {len(contact_text.split())} words")
            return scrape_contact_info_fallback()

        elif content_type == "general":
            text = ""
            target_elements = soup.select(selector) if selector else soup.find_all(['p', 'div', 'article', 'section'])
            for element in target_elements:
                element_text = element.get_text(separator=' ', strip=True).lower()
                if any(phrase in element_text for phrase in irrelevant_phrases):
                    continue
                if any(keyword.lower() in element_text for keyword in keywords):
                    text += element.get_text(separator=' ', strip=True) + " "
                    if len(text.split()) >= 30:
                        break
            text = ' '.join(text.split()).strip()
            if len(text.split()) >= 30:
                return text
            logging.warning(f"No general content found for keywords={keywords}")
            return f"Content for {', '.join(keywords)} is limited."

        logging.warning(f"Unknown content_type: {content_type}")
        return "Sorry, I couldn’t fetch the content."
    except Exception as e:
        logging.error(f"Scraping error for {url}: {e}")
        return scrape_contact_info_fallback() if content_type == "contact" else f"Sorry, I couldn’t fetch the content for {keywords[0]}."