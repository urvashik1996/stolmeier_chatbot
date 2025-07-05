import requests
from bs4 import BeautifulSoup
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
from thefuzz import fuzz
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_page_exists(url):
    """Check if a page exists using a HEAD request."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    for attempt in range(3):
        try:
            response = requests.head(url, timeout=10, headers=headers, allow_redirects=True)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/3 - Error checking if {url} exists: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
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
                time.sleep(2 ** attempt)
    
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"user-agent={headers['User-Agent']}")
        driver = webdriver.Chrome(options=options)
        driver.get(url)
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
        'Car Accidents': {'url': f"{main_url}car-accidents/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, section[class*="accident"], ul, ol'},
        'Medical Malpractice': {'url': f"{main_url}medical-malpractice/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, section[class*="malpractice"]'},
        'Slip Trip Fall': {'url': f"{main_url}slip-trip-or-fall/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, section[class*="slip"]'},
        'Truck Accidents': {'url': f"{main_url}truck-accidents/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, section[class*="truck"]'},
        '18-Wheeler Accidents': {'url': f"{main_url}18-wheeler-accidents/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, section[class*="wheeler"]'},
        'Motorcycle Accidents': {'url': f"{main_url}motorcycle-accidents/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, section[class*="motorcycle"]'},
        'Dog Bites & Attacks': {'url': f"{main_url}dog-bites-attacks/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, section[class*="dog"]'},
        'Product Liability': {'url': f"{main_url}product-liability/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, section[class*="product"]'},
        'Wrongful Death': {'url': f"{main_url}wrongful-death/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, section[class*="death"]'},
        'Recent Results': {'url': f"{main_url}recent-results/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, section[class*="results"]'},
        'About': {'url': f"{main_url}about/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, section[class*="about"]'},
        'Contact Us': {'url': f"{main_url}contact-us/", 'selector': 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, address, section[class*="contact"]'}
    }
    for section, data in website_map.items():
        if not check_page_exists(data['url']):
            logging.warning(f"URL {data['url']} not found for {section}")
            data['url'] = main_url
    return website_map

def scrape_contact_info_fallback():
    """Fallback for contact information."""
    return "Address: 219 E. Craig Place, San Antonio, TX 78212. Phone: 210-227-3612. Email: chris@stolmeierlaw.com."

def adjust_to_50_100_words(text, is_fallback=False, keyword=None):
    """Adjust text to 50-100 words, indicating if it's a fallback due to a missing page."""
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

def scrape_inner_links(url, keywords, content_type, max_links=3):
    """Scrape content from inner links on the page that match keywords."""
    try:
        keywords = [str(keyword) for keyword in keywords if keyword] if keywords else []
        html_content = fetch_page(url, use_selenium=False)
        if not html_content:
            html_content = fetch_page(url, use_selenium=True)
        if not html_content:
            logging.error(f"No content fetched from {url} for inner links")
            return None
        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.find_all('a', href=True)
        relevant_links = []
        for link in links:
            href = link['href']
            absolute_href = urljoin(url, href)
            link_text = link.get_text(strip=True).lower()
            if (any(keyword.lower() in href.lower() for keyword in keywords) or 
                any(keyword.lower() in link_text for keyword in keywords)) and check_page_exists(absolute_href):
                relevant_links.append(absolute_href)
        content = []
        for link_url in relevant_links[:max_links]:
            link_content = fetch_page(link_url, use_selenium=False)
            if not link_content:
                link_content = fetch_page(link_url, use_selenium=True)
            if link_content:
                soup = BeautifulSoup(link_content, 'html.parser')
                for element in soup.find_all(['nav', 'footer', 'header', 'form', 'iframe', 'script', 'style']):
                    element.decompose()
                for element in soup.find_all(['div', 'section'], class_=['menu', 'dropdown-menu', 'footer', 'sidebar', 'widget', 'related-posts', 'navbar', 'nav', 'top-bar', 'menu-item', 'nav-link', 'banner', 'slogan']):
                    element.decompose()
                if content_type in ["causes", "what to do", "injuries"]:
                    lists = soup.find_all(['ul', 'ol'])
                    for lst in lists:
                        if any(keyword.lower() in lst.get_text().lower() for keyword in keywords):
                            items = [li.get_text(strip=True) for li in lst.find_all('li') if li.get_text(strip=True)]
                            content.extend(items)
                else:
                    text = soup.get_text(separator=' ', strip=True)
                    if any(keyword.lower() in text.lower() for keyword in keywords):
                        content.append(text)
        if content:
            if content_type in ["causes", "what to do", "injuries"]:
                return "\n".join(f"- {item}" if content_type != "what to do" else f"{i+1}. {item}" for i, item in enumerate(content[:15]))
            return adjust_to_50_100_words(" ".join(content))
        logging.warning(f"No relevant content found in inner links for {keywords}")
        return None
    except Exception as e:
        logging.error(f"Error scraping inner links for {url}: {e}")
        return None

def scrape_targeted_content(keywords, content_type, session_id, url, website_map=None):
    """Scrape targeted content from the provided URL with keyword filtering."""
    logging.info(f"Scraping: keywords={keywords}, content_type={content_type}, url={url}")

    keywords = [str(keyword) for keyword in keywords if keyword] if keywords else []
    keyword_str = keywords[0] if keywords else 'your query'

    if not url:
        url = "https://stolmeierlaw.com/"
        logging.warning(f"No URL provided, using main URL: {url}")

    if not check_page_exists(url):
        logging.error(f"Page not found: {url}")
        if content_type == "contact":
            return scrape_contact_info_fallback()
        elif content_type == "description":
            main_url = "https://stolmeierlaw.com/"
            logging.info(f"Attempting to scrape main page {main_url} for {keywords}")
            content = scrape_inner_links(main_url, keywords, content_type)
            if content:
                return content
            return adjust_to_50_100_words(f"Our team will reach you soon regarding {keyword_str}. Contact Stolmeier Law at 210-227-3612 or chris@stolmeierlaw.com.", is_fallback=True, keyword=keyword_str)
        elif content_type == "causes":
            return "\n".join([
                "- Speeding",
                "- Impaired Driving",
                "- Drunk driving",
                "- Driving under the influence of narcotics",
                "- Sleep deprivation",
                "- Reckless Driving",
                "- Disregarding traffic signs and/or signals",
                "- Disregarding traffic lanes",
                "- Disregarding fellow motorists",
                "- Distracted Driving",
                "- Texting",
                "- Non-hands free phone calls",
                "- Eating",
                "- Changing the radio",
                "- Use of GPS"
            ])
        elif content_type == "what to do":
            return "\n".join([
                "1. Stop after the accident",
                "2. Assess yourself and your surroundings",
                "3. Contact the police",
                "4. Take pictures and videos",
                "5. Gather and exchange information",
                "6. Seek medical attention",
                "7. Contact your insurance company",
                "8. Contact experienced car accident lawyers"
            ])
        elif content_type == "injuries":
            return "\n".join([
                "- Strains and bruises",
                "- Lacerations",
                "- Ligament strains",
                "- Whiplash",
                "- Chest injuries",
                "- Burns",
                "- Broken bones",
                "- Neck injuries",
                "- Penetration injuries",
                "- Organ damage",
                "- Brain injuries",
                "- Loss of limb",
                "- Paralysis",
                "- Death"
            ])
        else:
            return adjust_to_50_100_words(f"Our team will reach you soon regarding {keyword_str}. Contact Stolmeier Law at 210-227-3612 or chris@stolmeierlaw.com.", is_fallback=True, keyword=keyword_str)

    try:
        html_content = fetch_page(url, use_selenium=False)
        if not html_content or len(html_content.strip()) < 100:
            logging.info("Content too short or empty, trying Selenium")
            html_content = fetch_page(url, use_selenium=True)
        if not html_content:
            logging.error(f"Failed to fetch content from {url}")
            return scrape_contact_info_fallback() if content_type == "contact" else adjust_to_50_100_words(f"Our team will reach you soon regarding {keyword_str}. Contact Stolmeier Law at 210-227-3612 or chris@stolmeierlaw.com.", is_fallback=True, keyword=keyword_str)

        soup = BeautifulSoup(html_content, 'html.parser')
        logging.debug(f"Parsed HTML content: {soup.get_text(separator=' ', strip=True)[:200]}...")

        meta_description = soup.find('meta', attrs={'name': 'description'})
        meta_content = meta_description['content'].strip() if meta_description and meta_description.get('content') else ""
        if content_type == "description" and meta_content and isinstance(meta_content, str) and len(meta_content.split()) >= 10:
            logging.info(f"Found meta description for {keywords}: {len(meta_content.split())} words")
            return adjust_to_50_100_words(meta_content)

        irrelevant_phrases = ['menu', 'home', 'lorem ipsum', 'your name', 'your email', 'your message', 'click here', 'read more', 'subscribe', 'login']
        for element in soup.find_all(['nav', 'footer', 'header', 'form', 'iframe', 'script', 'style', 'aside', 'div[class*="comment"]']):
            element.decompose()
        for element in soup.find_all(['div', 'section'], class_=[
            'menu', 'dropdown-menu', 'footer', 'sidebar', 'widget', 'related-posts', 'navbar', 'nav', 'top-bar',
            'menu-item', 'nav-link', 'banner', 'slogan', 'ad', 'advertisement'
        ]):
            element.decompose()

        selector = website_map.get(keywords[0], {}).get('selector', 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, h1, h2, h3, p, ul, ol') if website_map and keywords else 'main, div[class*="content"], div[class*="entry"], div[class*="page"], article, h1, h2, h3, p, ul, ol'

        def score_content(text, keywords):
            """Score content relevance based on keyword matches."""
            score = 0
            text_lower = text.lower()
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    score += fuzz.token_set_ratio(keyword.lower(), text_lower)
            return score

        if content_type == "causes" and "Car Accidents" in keywords:
            causes = []
            relevant_causes = [
                'speeding', 'impaired driving', 'drunk driving', 'distracted driving', 'texting',
                'reckless driving', 'sleep deprivation', 'disregarding traffic signs', 'eating',
                'changing the radio', 'use of gps', 'disregarding traffic lanes', 'disregarding fellow motorists'
            ]
            target_elements = soup.select(selector)
            for element in target_elements:
                element_text = element.get_text(separator=' ', strip=True).lower()
                if any(phrase in element_text for phrase in irrelevant_phrases):
                    continue
                if any(keyword.lower() in element_text for keyword in ['car accident', 'crash', 'causes']):
                    if element.name in ['ul', 'ol'] and element.find_all('li'):
                        li_texts = [li.get_text(strip=True) for li in element.find_all('li') if li.get_text(strip=True)]
                        causes.extend([text for text in li_texts if any(cause in text.lower() for cause in relevant_causes)])
                    elif any(cause in element_text for cause in relevant_causes):
                        causes.append(element.get_text(strip=True))
            causes = list(set(causes))
            if causes:
                logging.info(f"Scraped causes: {causes[:3]}...")
                return "\n".join(f"- {cause}" for cause in causes[:15]) if causes else "\n".join([
                    "- Speeding",
                    "- Impaired Driving",
                    "- Drunk driving",
                    "- Driving under the influence of narcotics",
                    "- Sleep deprivation",
                    "- Reckless Driving",
                    "- Disregarding traffic signs and/or signals",
                    "- Disregarding traffic lanes",
                    "- Disregarding fellow motorists",
                    "- Distracted Driving",
                    "- Texting",
                    "- Non-hands free phone calls",
                    "- Eating",
                    "- Changing the radio",
                    "- Use of GPS"
                ])
            logging.info(f"No causes found, trying inner links for {url}")
            inner_content = scrape_inner_links(url, keywords, content_type)
            if inner_content:
                return inner_content
            logging.warning(f"No causes found on {url} for Car Accidents")
            return "\n".join([
                "- Speeding",
                "- Impaired Driving",
                "- Drunk driving",
                "- Driving under the influence of narcotics",
                "- Sleep deprivation",
                "- Reckless Driving",
                "- Disregarding traffic signs and/or signals",
                "- Disregarding traffic lanes",
                "- Disregarding fellow motorists",
                "- Distracted Driving",
                "- Texting",
                "- Non-hands free phone calls",
                "- Eating",
                "- Changing the radio",
                "- Use of GPS"
            ])

        elif content_type == "what to do" and "Car Accidents" in keywords:
            steps = []
            relevant_steps = [
                'stop', 'assess', 'police', 'pictures', 'information', 'medical', 'insurance', 'lawyer'
            ]
            target_elements = soup.select(selector)
            for element in target_elements:
                element_text = element.get_text(separator=' ', strip=True).lower()
                if any(phrase in element_text for phrase in irrelevant_phrases):
                    continue
                if any(keyword.lower() in element_text for keyword in ['what to do', 'after accident', 'steps', 'car accident']):
                    if element.name in ['ol', 'ul'] and element.find_all('li'):
                        li_texts = [li.get_text(strip=True) for li in element.find_all('li') if li.get_text(strip=True)]
                        steps.extend([text for text in li_texts if any(step in text.lower() for step in relevant_steps)])
                    elif any(step in element_text for step in relevant_steps):
                        steps.append(element.get_text(strip=True))
            steps = list(set(steps))
            if steps:
                logging.info(f"Scraped steps: {steps[:3]}...")
                return "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps[:8])) if steps else "\n".join([
                    "1. Stop after the accident",
                    "2. Assess yourself and your surroundings",
                    "3. Contact the police",
                    "4. Take pictures and videos",
                    "5. Gather and exchange information",
                    "6. Seek medical attention",
                    "7. Contact your insurance company",
                    "8. Contact experienced car accident lawyers"
                ])
            logging.info(f"No steps found, trying inner links for {url}")
            inner_content = scrape_inner_links(url, keywords, content_type)
            if inner_content:
                return inner_content
            logging.warning(f"No steps found on {url} for what to do after a car accident")
            return "\n".join([
                "1. Stop after the accident",
                "2. Assess yourself and your surroundings",
                "3. Contact the police",
                "4. Take pictures and videos",
                "5. Gather and exchange information",
                "6. Seek medical attention",
                "7. Contact your insurance company",
                "8. Contact experienced car accident lawyers"
            ])

        elif content_type == "injuries" and "Car Accidents" in keywords:
            injuries = []
            relevant_injuries = [
                'strains', 'bruises', 'lacerations', 'ligament', 'whiplash', 'chest', 'burns',
                'broken bones', 'neck', 'penetration', 'organ damage', 'brain', 'loss of limb', 'paralysis', 'death'
            ]
            target_elements = soup.select(selector)
            for element in target_elements:
                element_text = element.get_text(separator=' ', strip=True).lower()
                if any(phrase in element_text for phrase in irrelevant_phrases):
                    continue
                if any(keyword.lower() in element_text for keyword in ['injury', 'injuries', 'car accident']):
                    if element.name in ['ul', 'ol'] and element.find_all('li'):
                        li_texts = [li.get_text(strip=True) for li in element.find_all('li') if li.get_text(strip=True)]
                        injuries.extend([text for text in li_texts if any(injury in text.lower() for injury in relevant_injuries)])
                    elif any(injury in element_text for injury in relevant_injuries):
                        injuries.append(element.get_text(strip=True))
            injuries = list(set(injuries))
            if injuries:
                logging.info(f"Scraped injuries: {injuries[:3]}...")
                return "\n".join(f"- {injury}" for injury in injuries[:15]) if injuries else "\n".join([
                    "- Strains and bruises",
                    "- Lacerations",
                    "- Ligament strains",
                    "- Whiplash",
                    "- Chest injuries",
                    "- Burns",
                    "- Broken bones",
                    "- Neck injuries",
                    "- Penetration injuries",
                    "- Organ damage",
                    "- Brain injuries",
                    "- Loss of limb",
                    "- Paralysis",
                    "- Death"
                ])
            logging.info(f"No injuries found, trying inner links for {url}")
            inner_content = scrape_inner_links(url, keywords, content_type)
            if inner_content:
                return inner_content
            logging.warning(f"No injuries found on {url} for Car Accidents")
            return "\n".join([
                "- Strains and bruises",
                "- Lacerations",
                "- Ligament strains",
                "- Whiplash",
                "- Chest injuries",
                "- Burns",
                "- Broken bones",
                "- Neck injuries",
                "- Penetration injuries",
                "- Organ damage",
                "- Brain injuries",
                "- Loss of limb",
                "- Paralysis",
                "- Death"
            ])

        else:
            content = []
            target_elements = soup.select(selector)
            for element in target_elements:
                element_text = element.get_text(separator=' ', strip=True)
                if any(phrase.lower() in element_text.lower() for phrase in irrelevant_phrases):
                    continue
                if any(keyword.lower() in element_text.lower() for keyword in keywords):
                    content.append(element_text)
            if content:
                logging.info(f"Scraped content for {keywords}: {content[:100]}...")
                return adjust_to_50_100_words(" ".join(content))
            logging.info(f"No content found, trying inner links for {url}")
            inner_content = scrape_inner_links(url, keywords, content_type)
            if inner_content:
                return inner_content
            logging.warning(f"No content found on {url} for {keywords}")
            return adjust_to_50_100_words(f"Our team will reach you soon regarding {keyword_str}. Contact Stolmeier Law at 210-227-3612 or chris@stolmeierlaw.com.", is_fallback=True, keyword=keyword_str)

    except Exception as e:
        logging.error(f"Error scraping targeted content for {url}: {e}")
        return scrape_contact_info_fallback() if content_type == "contact" else adjust_to_50_100_words(f"Our team will reach you soon regarding {keyword_str}. Contact Stolmeier Law at 210-227-3612 or chris@stolmeierlaw.com.", is_fallback=True, keyword=keyword_str)