import requests
from bs4 import BeautifulSoup
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_page_exists(url):
    """Check if a page exists using a HEAD request."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.head(url, timeout=10, headers=headers, allow_redirects=True)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Error checking if {url} exists: {e}")
        return False

def fetch_page(url, use_selenium=False, max_retries=3):
    """Fetch page content from URL using requests or Selenium with retries."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    if not use_selenium:
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=20, headers=headers)
                response.raise_for_status()
                return response.text
            except Exception as e:
                logging.error(f"Attempt {attempt + 1}/{max_retries} - Error fetching {url} with requests: {e}")
                if attempt == max_retries - 1:
                    logging.info("Falling back to Selenium for dynamic content")
                    break
                time.sleep(3)
    
    # Fallback to Selenium for dynamic content
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"user-agent={headers['User-Agent']}")
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        # Wait for main content to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "main, div[class*='content'], div[class*='entry'], div[class*='page'], article"))
        )
        html_content = driver.page_source
        driver.quit()
        return html_content
    except Exception as e:
        logging.error(f"Error fetching {url} with Selenium: {e}")
        return None

def build_website_map(main_url="https://stolmeierlaw.com/"):
    """Build a website map with specific URLs and selectors for each section."""
    logging.info(f"Building website map with main URL: {main_url}")
    website_map = {
        'Car Accidents': {'url': f"{main_url}car-accidents/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article'},
        'Medical Malpractice': {'url': f"{main_url}medical-malpractice/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article'},
        'Slip Trip Fall': {'url': f"{main_url}slip-and-fall/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article'},
        'Truck Accidents': {'url': f"{main_url}truck-accidents/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article'},
        '18-Wheeler Accidents': {'url': f"{main_url}18-wheeler-accidents/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article'},
        'Motorcycle Accidents': {'url': f"{main_url}motorcycle-accidents/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article'},
        'Dog Bites & Attacks': {'url': f"{main_url}dog-bites-attacks/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article'},
        'Product Liability': {'url': f"{main_url}product-liability/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article'},
        'Wrongful Death': {'url': f"{main_url}wrongful-death/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article'},
        'Recent Results': {'url': f"{main_url}recent-results/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article'},
        'About': {'url': f"{main_url}about/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article'},
        'Contact Us': {'url': f"{main_url}contact-us/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, address'}
    }
    return website_map

def scrape_contact_info_fallback():
    """Fallback for contact information."""
    return "Address: 219 E. Craig Place, San Antonio, TX 78212. Phone: 210-227-3612. Email: chris@stolmeierlaw.com."

def adjust_to_50_100_words(text, is_fallback=False, keyword=None):
    """Adjust text to 50-100 words, indicating if it's a fallback due to a missing page."""
    words = text.split()
    if len(words) > 100:
        return ' '.join(words[:100])
    elif len(words) < 50:
        padding = f"{'Page not found for ' + keyword + '. ' if is_fallback and keyword else ''}Stolmeier Law provides expert legal services in San Antonio, specializing in personal injury cases. Our experienced attorneys fight for your rights to secure fair compensation. Contact us for assistance with your legal needs."
        padding_words = padding.split()
        words.extend(padding_words[:50 - len(words)])
        return ' '.join(words)
    return text

def scrape_targeted_content(keywords, content_type, session_id, url, website_map=None):
    """Scrape targeted content from the provided URL with keyword filtering."""
    logging.info(f"Scraping: keywords={keywords}, content_type={content_type}, url={url}")

    if not url:
        url = "https://stolmeierlaw.com/"
        logging.warning(f"No URL provided, using main URL: {url}")

    # Check if the page exists
    if not check_page_exists(url):
        logging.error(f"Page not found: {url}")
        if content_type == "contact":
            return scrape_contact_info_fallback()
        elif content_type == "description":
            # Try scraping the main page for related content
            main_url = "https://stolmeierlaw.com/"
            logging.info(f"Attempting to scrape main page {main_url} for {keywords}")
            html_content = fetch_page(main_url, use_selenium=False)
            if not html_content or len(html_content.strip()) < 100:
                html_content = fetch_page(main_url, use_selenium=True)
            if not html_content:
                return adjust_to_50_100_words(f"Page not found for {keywords[0]}.", is_fallback=True, keyword=keywords[0])
        else:
            return adjust_to_50_100_words(f"Page not found for {keywords[0]}.", is_fallback=True, keyword=keywords[0])

    try:
        # Try static scraping first, then fallback to Selenium
        html_content = fetch_page(url, use_selenium=False)
        if not html_content or len(html_content.strip()) < 100:
            logging.info("Content too short or empty, trying Selenium")
            html_content = fetch_page(url, use_selenium=True)
        if not html_content:
            logging.error(f"Failed to fetch content from {url}")
            return scrape_contact_info_fallback() if content_type == "contact" else adjust_to_50_100_words(f"Page not found for {keywords[0]}.", is_fallback=True, keyword=keywords[0])

        soup = BeautifulSoup(html_content, 'html.parser')
        logging.debug(f"Parsed HTML content: {soup.get_text(separator=' ', strip=True)[:200]}...")

        # Check for meta description first
        meta_description = soup.find('meta', attrs={'name': 'description'})
        meta_content = meta_description['content'].strip() if meta_description and meta_description.get('content') else ""
        if content_type == "description" and meta_content and len(meta_content.split()) >= 10:
            logging.info(f"Found meta description for {keywords}: {len(meta_content.split())} words")
            return adjust_to_50_100_words(meta_content)

        # Remove irrelevant structural elements
        irrelevant_phrases = ['menu', 'home', 'lorem ipsum', 'your name', 'your email', 'your message']
        for element in soup.find_all(['nav', 'footer', 'header', 'form', 'iframe', 'script', 'style']):
            element.decompose()
        for element in soup.find_all(['div', 'section'], class_=[
            'menu', 'dropdown-menu', 'footer', 'sidebar', 'widget', 'related-posts', 'navbar', 'nav', 'top-bar',
            'menu-item', 'nav-link', 'banner', 'slogan'
        ]):
            element.decompose()

        # Use selector from website_map if available
        selector = website_map.get(keywords[0], {}).get('selector', 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article') if website_map and keywords else 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article'

        if content_type == "causes" and "Car Accidents" in keywords:
            causes = []
            relevant_causes = [
                'speeding', 'impaired driving', 'drunk driving', 'distracted driving', 'texting',
                'reckless driving', 'sleep deprivation', 'disregarding traffic signs', 'eating',
                'changing the radio', 'use of gps', 'disregarding traffic lanes', 'disregarding fellow motorists'
            ]
            target_elements = soup.select(selector)
            for section in target_elements:
                section_text = section.get_text(separator=' ', strip=True).lower()
                if any(phrase in section_text for phrase in irrelevant_phrases):
                    continue
                if any(keyword.lower() in section_text for keyword in ['car accident', 'crash', 'causes']):
                    if section.name == 'ul' and section.find_all('li'):
                        li_texts = [li.get_text(separator=' ', strip=True) for li in section.find_all('li')]
                        causes.extend([text for text in li_texts if any(cause in text.lower() for cause in relevant_causes)])
                    elif any(cause in section_text for cause in relevant_causes):
                        causes.append(section.get_text(separator=' ', strip=True))
            causes = list(set(causes))
            if causes:
                logging.info(f"Scraped causes: {causes[:3]}...")
                return adjust_to_50_100_words("; ".join(causes))
            logging.warning(f"No causes found on {url} for Car Accidents")
            return adjust_to_50_100_words("Common causes of car accidents include speeding, distracted driving, and impaired driving. Contact Stolmeier Law for assistance.")

        elif content_type == "description":
            text = ""
            target_elements = soup.select(selector)
            for section in target_elements:
                section_text = section.get_text(separator=' ', strip=True).lower()
                if any(phrase in section_text for phrase in irrelevant_phrases):
                    continue
                # Ensure content is relevant to the keyword
                if any(keyword.lower() in section_text for keyword in keywords) or not keywords:
                    text += section.get_text(separator=' ', strip=True) + " "
                if len(text.split()) >= 200:
                    break
            text = ' '.join(text.split()).strip()
            word_count = len(text.split())
            if word_count >= 20:
                logging.info(f"Scraped description for {keywords}: {word_count} words")
                return adjust_to_50_100_words(text)
            logging.warning(f"Description for {keywords} has only {word_count} words")
            # Try main page as a fallback
            main_url = "https://stolmeierlaw.com/"
            if url != main_url and check_page_exists(main_url):
                logging.info(f"Attempting to scrape main page {main_url} for {keywords}")
                html_content = fetch_page(main_url, use_selenium=False)
                if not html_content or len(html_content.strip()) < 100:
                    html_content = fetch_page(main_url, use_selenium=True)
                if html_content:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    for element in soup.find_all(['nav', 'footer', 'header', 'form', 'iframe', 'script', 'style']):
                        element.decompose()
                    for element in soup.find_all(['div', 'section'], class_=[
                        'menu', 'dropdown-menu', 'footer', 'sidebar', 'widget', 'related-posts', 'navbar', 'nav', 'top-bar',
                        'menu-item', 'nav-link', 'banner', 'slogan'
                    ]):
                        element.decompose()
                    target_elements = soup.select(selector)
                    text = ""
                    for section in target_elements:
                        section_text = section.get_text(separator=' ', strip=True).lower()
                        if any(phrase in section_text for phrase in irrelevant_phrases):
                            continue
                        if any(keyword.lower() in section_text for keyword in keywords) or not keywords:
                            text += section.get_text(separator=' ', strip=True) + " "
                        if len(text.split()) >= 200:
                            break
                    text = ' '.join(text.split()).strip()
                    word_count = len(text.split())
                    if word_count >= 20:
                        logging.info(f"Scraped description from main page for {keywords}: {word_count} words")
                        return adjust_to_50_100_words(f"Page not found for {keywords[0]}. {text}", is_fallback=True, keyword=keywords[0])
            # Fallback descriptions
            fallback_content = {
                'Car Accidents': "Stolmeier Law in San Antonio helps car accident victims seek compensation for injuries, medical expenses, and lost wages. Our experienced attorneys fight for your rights against negligent drivers. Contact us for expert legal support.",
                'Medical Malpractice': "Stolmeier Law assists victims of medical malpractice in San Antonio, pursuing compensation for injuries caused by negligent healthcare providers. With over 35 years of experience, we maximize your recovery. Contact us for dedicated legal representation.",
                'Slip Trip Fall': "Page not found for Slip Trip Fall. Stolmeier Law represents San Antonio clients injured in slip and fall accidents, securing compensation for injuries and damages. Our experienced attorneys ensure your rights are protected.",
                'Truck Accidents': "Stolmeier Law fights for victims of truck accidents in San Antonio. These involve larger vehicles, causing severe injuries. We prove liability and maximize compensation with over 35 years of experience. Contact us for expert support.",
                '18-Wheeler Accidents': "Stolmeier Law handles 18-wheeler accident cases in San Antonio, addressing severe injuries from large trucks. Our experienced attorneys fight for your compensation with proven expertise. Contact us for legal support.",
                'Motorcycle Accidents': "Stolmeier Law supports San Antonio motorcycle accident victims, seeking compensation for injuries and damages. Our attorneys provide expert representation to protect your rights.",
                'Dog Bites & Attacks': "Stolmeier Law represents San Antonio clients injured by dog bites or attacks, securing compensation for medical expenses and pain. Contact us for experienced legal support.",
                'Product Liability': "Stolmeier Law assists San Antonio clients with product liability claims, seeking compensation for injuries caused by defective products. Our attorneys fight for your rights.",
                'Wrongful Death': "Stolmeier Law supports San Antonio families pursuing wrongful death claims, seeking justice and compensation for their loss with over 35 years of experience.",
                'Recent Results': "Stolmeier Law has a strong track record in San Antonio, securing favorable outcomes for personal injury clients. Contact us to learn about our successful case results.",
                'About': "Stolmeier Law, a San Antonio-based firm, specializes in personal injury cases like car accidents and medical malpractice. Our dedicated attorneys provide expert representation."
            }
            return adjust_to_50_100_words(fallback_content.get(keywords[0], f"Page not found for {keywords[0]}. Stolmeier Law provides expert legal services."), is_fallback=True, keyword=keywords[0])

        elif content_type == "contact":
            contact_text = ""
            target_elements = soup.select(selector)
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
            target_elements = soup.select(selector)
            for element in target_elements:
                element_text = section.get_text(separator=' ', strip=True).lower()
                if any(phrase in element_text for phrase in irrelevant_phrases):
                    continue
                if any(keyword.lower() in element_text for keyword in keywords) or not keywords:
                    text += element.get_text(separator=' ', strip=True) + " "
                if len(text.split()) >= 200:
                    break
            text = ' '.join(text.split()).strip()
            if len(text.split()) >= 20:
                return adjust_to_50_100_words(text)
            logging.warning(f"No general content found for keywords={keywords}")
            return adjust_to_50_100_words(f"Content for {', '.join(keywords)} is limited.")

        logging.warning(f"Unknown content_type: {content_type}")
        return adjust_to_50_100_words(f"Page not found for {keywords[0]}.", is_fallback=True, keyword=keywords[0])
    except Exception as e:
        logging.error(f"Scraping error for {url}: {e}")
        return scrape_contact_info_fallback() if content_type == "contact" else adjust_to_50_100_words(f"Page not found for {keywords[0]}.", is_fallback=True, keyword=keywords[0])