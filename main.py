import flask
from flask import Flask, request, jsonify
from flask import send_from_directory
from requests_html import HTMLSession
import time
import json
import logging
import pytz
from datetime import datetime
import random
import requests
import functools
import os
import dotenv
import html
from logging.handlers import RotatingFileHandler  # Added for log rotation
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import xml.etree.ElementTree as ET

dotenv.load_dotenv()

# ================ LOGGING INITIATION ================
logger = logging.getLogger('BBC-API')
logger.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler('api.log', maxBytes=10 * 1024, backupCount=0)
file_handler.setLevel(logging.DEBUG)  # Log all levels to the file

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # Log INFO and above to the console

custom_format = '%(asctime)s - %(filename)s - %(levelname)s - %(message)s'

class ColoredFormatter(logging.Formatter):
    # Define color codes for different log levels
    LEVEL_COLORS = {
        'DEBUG': '\033[34m',    # Blue
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[41m'  # Red background
    }

    MESSAGE_COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m'  # Magenta
    }
    
    RESET = '\033[0m'  # Reset color

    def format(self, record):
        # Get the color for the log level and message based on the level name
        level_color = self.LEVEL_COLORS.get(record.levelname, self.RESET)
        message_color = self.MESSAGE_COLORS.get(record.levelname, self.RESET)

        # Format the message with the colors
        log_fmt = (
            f'\033[1;34m%(asctime)s\033[0m - \033[1;36m%(filename)s\033[0m - '
            f'{level_color}\033[1m%(levelname)s\033[0m - '
            f'{message_color}%(message)s{self.RESET}'
        )
        
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

formatter = logging.Formatter(custom_format)

file_handler.setFormatter(formatter)
console_handler.setFormatter(ColoredFormatter())

# Define a custom logging filter to add the filename
class NoFlaskFilter(logging.Filter):
    def __init__(self, name: str = None) -> None:
        self.name = name if name is not None else __file__
        super().__init__(name)
    
    def filter(self, record):
        record.filename = f"{self.name}"
        message = record.getMessage()
        return True and (not ("HTTP/1.1" in message and ("GET" in message or "OPTIONS *")))

console_handler.addFilter(NoFlaskFilter("ENDPOINT"))
file_handler.addFilter(NoFlaskFilter("ENDPOINT"))

logger.addHandler(file_handler)
logger.addHandler(console_handler)


# ================ FLASK INITIATION ================
app = Flask(__name__, static_folder="templates", static_url_path="/static")
session = HTMLSession()

# Simple in-memory cache for image URLs to avoid repeated scraping
image_cache = {}

# Cache for resolved real URLs from Google News URLs
url_cache = {}

# ================ DHAKA TIME ================
def ctime():
    timezone = pytz.timezone("Asia/Dhaka")
    ctime = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S ")
    return ctime


# ---------------- URL Dict ----------------
urls = {
    "arabic": "https://www.bbc.com/arabic",
    "chinese": "https://www.bbc.com/zhongwen/simp",
    "indonesian": "https://www.bbc.com/indonesia",
    "kyrgyz": "https://www.bbc.com/kyrgyz",
    "persian": "https://www.bbc.com/persian",
    "somali": "https://www.bbc.com/somali",
    "turkish": "https://www.bbc.com/turkce",
    "vietnamese": "https://www.bbc.com/vietnamese",
    "azeri": "https://www.bbc.com/azeri",
    "french": "https://www.bbc.com/afrique",
    "japanese": "https://www.bbc.com/japanese",
    "marathi": "https://www.bbc.com/marathi",
    "portuguese": "https://www.bbc.com/portuguese",
    "spanish": "https://www.bbc.com/mundo",
    "ukrainian": "https://www.bbc.com/ukrainian",
    "bengali": "https://bbc.com/bengali",
    "hausa": "https://bbc.com/hausa",
    "kinyarwanda": "https://bbc.com/gahuza",
    "nepali": "https://bbc.com/nepali",
    "russian": "https://bbc.com/russian",
    "swahili": "https://bbc.com/swahili",
    "urdu": "https://www.bbc.com/urdu",
    "burmese": "https://bbc.com/burmese",
    "hindi": "https://bbc.com/hindi",
    "kirundi": "https://bbc.com/gahuza",
    "pashto": "https://bbc.com/pashto",
    "sinhala": "https://bbc.com/sinhala",
    "tamil": "https://bbc.com/tamil",
    "uzbek": "https://bbc.com/uzbek",
    "english": "https://bbc.com",
    "yoruba": "https://www.bbc.com/yoruba"
}

# ================ HELPING FUNCTIONS ================

def visit_register(func):
    pass
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)

        if result[0].get("isBot") != "YES" and "Shields" not in str(result[0].get("User-Agent")):
            requests.post(
                f"https://web-badge-psi.vercel.app/register-visit?api_key={os.environ.get('API_KEY')}",
                headers=json.loads(os.environ.get("HEADERS")),
                json={
                    'func_name': str(func.__name__)
                }
            )
        return result[1]
    return wrapper

def resolve_real_article_url(google_url):
    """Resolve Google News URL to real article URL using redirects or decoding"""
    if google_url in url_cache:
        print(f"Found cached real URL for {google_url}: {url_cache[google_url]}")
        return url_cache[google_url]

    try:
        # Option A: Follow redirects (simplest and most reliable)
        print(f"Following redirects for: {google_url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        response = requests.get(google_url, headers=headers, timeout=5, allow_redirects=True)
        final_url = response.url

        # Check if we successfully redirected to a non-Google URL
        if not final_url.startswith('https://news.google.com'):
            print(f"Successfully resolved to real URL: {final_url}")
            url_cache[google_url] = final_url
            return final_url
        else:
            print("Redirect didn't work, final URL still Google News. Trying manual decoding...")

    except Exception as e:
        print(f"Redirect failed: {e}. Trying manual decoding...")

    # Option B: Manual base64 decoding fallback
    try:
        import base64
        import re

        # Extract the base64 encoded part after /articles/
        if '/articles/' in google_url:
            encoded_part = google_url.split('/articles/')[1].split('?')[0]
            print(f"Attempting to decode base64 part: {encoded_part[:50]}...")

            # Try to decode the base64 string
            try:
                decoded_bytes = base64.urlsafe_b64decode(encoded_part + '==')
                decoded_text = decoded_bytes.decode('utf-8', errors='ignore')
                print(f"Decoded text preview: {repr(decoded_text[:100])}")

                # Look for URLs in the decoded text
                url_patterns = [
                    r'https?://[^\x00-\x1f\x7f-\x9f\s\"\'<>]+',  # Basic URL pattern
                    r'https?://[^\s\"\'<>]+',  # URL without control chars
                ]

                for pattern in url_patterns:
                    urls = re.findall(pattern, decoded_text)
                    if urls:
                        print(f"Found potential URLs with pattern: {len(urls)}")
                        for url in urls[:3]:  # Check first few URLs
                            print(f"  Testing URL: {url[:100]}...")
                            # Validate the URL by making a quick HEAD request
                            try:
                                test_response = requests.head(url, timeout=3, allow_redirects=True)
                                if test_response.status_code == 200:
                                    print(f"  Valid real URL found: {url}")
                                    url_cache[google_url] = url
                                    return url
                            except:
                                continue

            except Exception as decode_e:
                print(f"Base64 decoding failed: {decode_e}")

    except Exception as e:
        print(f"Manual decoding failed: {e}")

    # If all methods fail, return the original URL
    print(f"All resolution methods failed, using original URL: {google_url}")
    url_cache[google_url] = google_url
    return google_url

def get_article_image(url):
    """Extract image from article URL with proper URL resolution and caching"""
    print(f"Attempting to get image for URL: {url}")
    if url in image_cache:
        print(f"Found cached image for {url}: {image_cache[url]}")
        return image_cache[url]

    try:
        # Resolve Google News URL to real article URL first
        real_url = resolve_real_article_url(url)
        print(f"Resolved URL: {real_url}")

        # Now fetch the real article page for og:image
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        print(f"Fetching article page: {real_url}")
        response = requests.get(real_url, headers=headers, timeout=8)
        print(f"Response status: {response.status_code}, final URL: {response.url}")

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Try Open Graph image first (most reliable)
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                image_url = og_image['content']
                # Ensure it's a full URL
                if image_url.startswith('http'):
                    print(f"Found og:image: {image_url}")
                    image_cache[url] = image_url
                    return image_url

            # Try Twitter image as fallback
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                image_url = twitter_image['content']
                if image_url.startswith('http'):
                    print(f"Found twitter:image: {image_url}")
                    image_cache[url] = image_url
                    return image_url

            # Try first img tag with reasonable size as last resort
            img_tags = soup.find_all('img')
            for img in img_tags:
                img_src = img.get('src')
                if img_src:
                    if img_src.startswith('http'):
                        full_url = img_src
                    elif img_src.startswith('//'):
                        full_url = 'https:' + img_src
                    else:
                        full_url = urljoin(response.url, img_src)

                    # Check if image is reasonably sized (not icons)
                    width = img.get('width')
                    height = img.get('height')
                    if width and height:
                        try:
                            w = int(width)
                            h = int(height)
                            if w >= 200 and h >= 150:  # Minimum size for article images
                                print(f"Found suitable img tag: {full_url}")
                                image_cache[url] = full_url
                                return full_url
                        except:
                            pass
                    else:
                        # If no dimensions, check if it looks like a content image
                        if 'article' in img_src.lower() or 'content' in img_src.lower() or 'photo' in img_src.lower():
                            print(f"Found content img tag: {full_url}")
                            image_cache[url] = full_url
                            return full_url

        print(f"No image found for {url}")
        # Cache empty result to avoid repeated failed attempts
        image_cache[url] = ''
        return ''

    except Exception as e:
        print(f"Error getting image from {url}: {e}")
        image_cache[url] = ''
        return ''

def _get(lang, latest):
    start = time.time()
    response = {}
    try:
        with HTMLSession() as session:
            r = session.get(lang)
            response["status"] = r.status_code
            if r.status_code == 200:
                sections = r.html.find('section[aria-labelledby]:not([data-testid])')
                checked, method_2 = False, False
                for section in sections:
                    title = section.find("h2", first=True).text
                    news_lis = section.find('li:not(role)')
                    news_lis = [li for li in news_lis if any(cls.startswith('bbc-') for cls in li.attrs.get('class', [])) and 'role' not in li.attrs]
                    if not checked and news_lis[0].find('div[data-e2e="story-promo"]'):
                        checked, method_2 = True, True
                    else:
                        checked = True
                    section_news = []
                    if not method_2:
                        for news_li in news_lis:
                            image_link = news_li.find('div.promo-image', first=True).find('img', first=True).attrs.get('src')
                            promo_div = news_li.find('div.promo-text', first=True)
                            title_tag = promo_div.find('h3 a', first=True)
                            news_title = title_tag.text
                            news_link = list(title_tag.absolute_links)[0]
                            summary_tag = promo_div.find('p', first=True)
                            news_summary = summary_tag.text if summary_tag else None
                            section_news.append({
                                "title": news_title,
                                "summary": news_summary,
                                "news_link": news_link,
                                "image_link": image_link
                            })
                    elif method_2:
                        for news_li in news_lis:
                            news_li = news_li.find('div[data-e2e="story-promo"]', first=True)
                            image_link = news_li.find('img', first=True).attrs.get('src')
                            title_tag = news_li.find('h3 a', first=True)
                            news_title = title_tag.text
                            news_link = list(title_tag.absolute_links)[0]
                            summary_tag = news_li.find('p', first=True)
                            news_summary = summary_tag.text if summary_tag else None
                            section_news.append({
                                "title": news_title,
                                "summary": news_summary,
                                "news_link": news_link,
                                "image_link": image_link
                            })
                    if section_news:
                        response[title] = section_news
                    if latest:
                        break
            else:
                response['status'] = 503
                response["error"] = f"Failed to retrieve content. BBC website returned status code: {r.status_code}"
    except Exception as e:
        response["status"] = 500
        response["error"] = str(e)
    end = time.time()
    duration = end - start
    response["elapsed time"] = f"{duration:.3f}s"
    response["timestamp"] = int(time.time())
    return response

def get_eng(latest):
    def extract_info_from_div(div):
        heading = div.find('h2[data-testid="card-headline"]', first=True)
        heading_text = heading.text if heading else None
        summary = div.find('p[data-testid="card-description"]', first=True)
        summary_text = summary.text if summary else None
        images = div.find('img')
        image_src = None
        for image in images:
            if image:
                if 'srcset' in image.attrs and image.attrs['srcset']:
                    image_src = image.attrs['srcset'].split(',')[0].split(' ')[0]
                else:
                    image_src = image.attrs.get('src', None)
        link = div.find('a', first=True)
        news_link = link.attrs['href'] if link else None
        return heading_text, summary_text, image_src, news_link

    response = {}
    start = time.time()
    try:
        with HTMLSession() as session:
            r = session.get('https://www.bbc.com/')
            if r.status_code != 200:
                response["status"] = 503
                response["error"] = f"Failed to retrieve content. BBC website returned status code: {r.status_code}"
                return response
            divs = r.html.find('div')
            section_divs = [div for div in divs if div.attrs.get('data-testid', '').endswith('-section')]
            response["status"] = r.status_code
            for section_div in section_divs:
                title_wrapper_divs = section_div.find('div')
                titles = [title for title in title_wrapper_divs if title.attrs.get('data-testid', '').endswith('-title-wrapper')]
                if not titles:  # For the latest category
                    sec_news = []
                    cards = section_div.find('div[data-testid$="-card"]')
                    for card in cards:
                        heading, summary, image, news_link = extract_info_from_div(card)
                        sec_news.append({
                            "title": heading,
                            "summary": summary,
                            "image_link": image,
                            "news_link": f"{urls['english']}{news_link}"
                        })
                    response["Latest"] = sec_news
                    if latest:
                        break
                else:
                    for title_wrapper in titles:
                        sec_news = []
                        title = title_wrapper.find('h2', first=True)
                        title_text = title.text if title else "Untitled"
                        cards = section_div.find('div[data-testid$="-card"]')
                        for card in cards:
                            heading, summary, image, news_link = extract_info_from_div(card)
                            sec_news.append({
                                "title": heading,
                                "summary": summary,
                                "image_link": image,
                                "news_link": f"{urls['english']}{news_link}"
                            })
                        response[title_text] = sec_news
            response = {k: v for k, v in response.items() if v not in [None, []]}
    except Exception as e:
        response["status"] = 500
        response["error"] = str(e)
    end = time.time()
    response["elapsed time"] = f"{end - start:.3f}s"
    response["timestamp"] = int(time.time())
    return response


# ================ ENDPOINTS ================

@app.route("/")
def index():
    return flask.render_template("index.html")

@app.route("/ping")
async def ping():
    logger.info(f"{ctime()}: Ping endpoint called - 200")

    return flask.Response(
        json.dumps({"status": 200}, ensure_ascii=False),
        mimetype="application/json; charset=utf-8",
        status=200,
    )

@app.route("/doc")
@app.route("/doc/")
@app.route("/docs")
@app.route("/docs/")
@app.route("/documentation")
@app.route("/documentation/")
async def doc():
    lang = random.choice(list(urls.keys()))
    logger.info(f"{ctime()}: DOC endpoint called - 200")
    return flask.render_template("documentation.html", listOfLangs="\n".join([f"<li>{key.capitalize()}: <code>{key}</code></li>" for key in sorted(urls.keys())]), type="{type}", language="{language}", lang=lang.title(), urlForNews=f"https://{(flask.request.url).split('/')[2]}/news?lang={lang}", urlForLatest=f"https://{(flask.request.url).split('/')[2]}/latest?lang={lang}", currentYear=str(datetime.now(pytz.timezone("Asia/Dhaka")).year))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype='image/vnd.microsoft.icon')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(app.static_folder, "sitemap.xml", mimetype='application/xml')


@app.route('/news', methods=['GET', 'OPTIONS'])
def news():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        # Get parameters (GNews-compatible)
        query = request.args.get('q', '')
        topic = request.args.get('topic', '')
        country = request.args.get('country', 'GB')  # Default to GB for BBC
        language = request.args.get('language', 'en')
        max_results = int(request.args.get('max_results', 10))

        # Fetch BBC news data
        bbc_data = get_eng(False)  # Get all sections

        if bbc_data.get('status') != 200:
            return jsonify({'error': 'Failed to fetch BBC news'}), 500

        # Transform BBC data to GNews format
        articles = transform_bbc_to_gnews_format(bbc_data, query, topic, max_results)

        if not articles:
            return jsonify({'error': 'No articles found'}), 404

        return jsonify({'articles': articles})

    except ValueError as e:
        if 'max_results' in str(e):
            return jsonify({'error': 'Invalid max_results. Must be a positive integer.'}), 400
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/extract', methods=['GET'])
def extract():
    """Extract article content and image from URL (same as GNews)"""
    try:
        url = request.args.get('url')
        if not url:
            return jsonify({'error': 'URL parameter required'}), 400

        # Extract content from BBC article
        content_data = extract_bbc_article_content(url)

        return jsonify(content_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def transform_bbc_to_gnews_format(bbc_data, query, topic, max_results):
    """Transform BBC API response to GNews article format"""
    articles = []

    # Map topic to BBC sections
    topic_mapping = {
        'general': ['Latest', 'Top Stories'],
        'technology': ['Technology'],
        'science': ['Science'],
        'business': ['Business'],
        'politics': ['Politics'],
        'world': ['World'],
        'health': ['Health'],
        'entertainment': ['Entertainment'],
        'sports': ['Sport'],
        'geopolitics': ['World', 'Politics'],
    }

    # Get relevant sections based on topic
    relevant_sections = topic_mapping.get(topic.lower(), list(bbc_data.keys()))

    # Filter out non-section keys
    relevant_sections = [s for s in relevant_sections if s in bbc_data and isinstance(bbc_data[s], list)]

    article_count = 0

    for section_name in relevant_sections:
        if article_count >= max_results:
            break

        section_articles = bbc_data[section_name]
        if not isinstance(section_articles, list):
            continue

        for bbc_article in section_articles:
            if article_count >= max_results:
                break

            # Skip articles with no title
            if not bbc_article.get('title'):
                continue

            # Transform to GNews format
            article = {
                'title': bbc_article.get('title') or '',
                'description': bbc_article.get('summary') or '',
                'url': bbc_article.get('news_link') or '',
                'urlToImage': get_article_image(bbc_article.get('news_link') or ''),
                'publishedAt': datetime.now(pytz.timezone("Asia/Dhaka")).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'BBC News',
                'source': 'BBC News',
                'category': topic.lower() if topic else 'general',
                'region': 'global',
                'tags': [section_name.lower()],
                'readTime': len(bbc_article.get('summary') or '') // 200 + 1,
                'aiSummary': ''
            }

            # Apply query filter if specified
            if query:
                search_text = (article['title'] + ' ' + article['description']).lower()
                if query.lower() not in search_text:
                    continue

            articles.append(article)
            article_count += 1

    return articles

def extract_bbc_article_content(url):
    """Extract full article content and main image from BBC article URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            return {'content': '', 'image': ''}

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract main image
        main_image = ''
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            main_image = og_image['content']

        # Extract article content
        content_parts = []

        # Try different content selectors for BBC articles
        content_selectors = [
            'div[data-component="text-block"] p',
            'div[data-component="text"] p',
            '.article__body p',
            '.story-body p',
            '.story-body__inner p',
            '[data-component="text-block"] p',
        ]

        for selector in content_selectors:
            paragraphs = soup.select(selector)
            if paragraphs:
                content_parts.extend([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
                break

        # Fallback: look for any paragraph in main content area
        if not content_parts:
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='article')
            if main_content:
                paragraphs = main_content.find_all('p')
                content_parts = [p.get_text().strip() for p in paragraphs if p.get_text().strip()]

        # Format as HTML
        if content_parts:
            html_content = '<div>' + ''.join([f'<p>{p}</p>' for p in content_parts]) + '</div>'
        else:
            html_content = '<p>The full article content is currently inaccessible. This could be due to access restrictions or technical issues. For the complete story, please visit the original source.</p>'

        return {
            'content': html_content,
            'image': main_image
        }

    except Exception as e:
        print(f"Error extracting BBC article content: {e}")
        return {
            'content': '<p>Unable to extract article content. Please visit the original BBC article for the full story.</p>',
            'image': ''
        }

@app.route("/log/", defaults={"pin": None})
@app.route("/log/<pin>")
@app.route("/logs/", defaults={"pin": None})
@app.route("/logs/<pin>")
@visit_register
async def log(pin):
    if pin != None and int(pin) == int(os.environ["PIN"]):
        with open("api.log", "r", encoding="utf-8") as f:
            logs = f.read()
        logs = html.escape(logs).replace("\n", "<br>")
        logger.info(f"{ctime()}: LOG endpoint called - 200")
        return (safe_headers(), flask.Response(logs, mimetype="text/html; charset=utf-8", status=200))
    else:
        logger.info(
            f"{ctime()}: LOG endpoint called - 400 (Authorization Failed)"
        )
        return (safe_headers(), flask.Response(
            json.dumps(
                {"status": 400, "error": "Authorization Failed"}, ensure_ascii=False
            ),
            mimetype="application/json; charset=utf-8",
            status=400,
        ))

# Serve static files for index page
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

@app.route("/languages")
@visit_register
async def languages():
    response = {
        "status": 200,
        "languages": [
            {
                "code": code,
                "name": code.capitalize(),
                "url": url,
                "description": f"BBC News in {code.capitalize()}"
            }
            for code, url in urls.items()
        ]
    }
    return (safe_headers(), flask.Response(
        json.dumps(response, ensure_ascii=False).encode("utf8"),
        mimetype="application/json; charset=utf-8",
        status=200,
    ))

# Legacy endpoint for backward compatibility
@app.route("/", defaults={"type": None})
@app.route("/<type>")
@visit_register
async def legacy_news(type):
    if type == "favicon.ico":
        return (safe_headers(), "None")

    if type not in ['latest', 'news']:
        logger.info(
            f"{ctime()}: NEWS endpoint called - 400 (Invalid Type)"
        )
        return (safe_headers(), flask.Response(
            json.dumps(
                {"status": 400, "error": "Invalid Type!", "types": ["news", "latest"]},
                ensure_ascii=False,
            ).encode("utf8"),
            mimetype="application/json; charset=utf-8",
            status=400,
        ))
    language = flask.request.args.get('lang')

    if language is None:
        logger.info(
            f"{ctime()}: NEWS (Type: {type}) endpoint called - 400 (Language Parameter Missing)"
        )
        return (safe_headers(), flask.Response(
            json.dumps(
                {
                    "status": 400,
                    "error": "Language Parameter Required!",
                    "example url": f"https://{(flask.request.url).split('/')[2]}/{type}?lang=<language>",
                    "supported languages": f"https://{(flask.request.url).split('/')[2]}/doc#languages"
                },
                ensure_ascii=False,
            ).encode("utf8"),
            mimetype="application/json; charset=utf-8",
            status=400,
        ))
    if str(language).lower() not in urls:
        logger.info(
            f"{ctime()}: NEWS (Type: {type}) endpoint called - 400 (Invalid Language)"
        )
        return (safe_headers(), flask.Response(
            json.dumps(
                {
                    "status": 400,
                    "error": "Invalid Language!",
                    "supported languages": f"https://{(flask.request.url).split('/')[2]}/doc#languages",
                },
                ensure_ascii=False,
            ).encode("utf8"),
            mimetype="application/json; charset=utf-8",
            status=400,
        ))

    if str(type) == "news":
        if str(language).lower() == 'english':
            response = get_eng(False)
        else:
            response = _get(urls[str(language).lower()], False)
        logger.info(
            f"{ctime()}: NEWS (language: {language}, type: {type}) endpoint called - 200"
        )
        return (safe_headers(), flask.Response(
            json.dumps(response, ensure_ascii=False).encode("utf8"),
            mimetype="application/json; charset=utf-8",
            status=response['status'],
        ))
    elif str(type) == "latest":
        if str(language).lower() == 'english':
            response = get_eng(True)
        else:
            response = _get(urls[str(language).lower()], True)

        logger.info(
            f"{ctime()}: NEWS (language: {language}, type: {type}) endpoint called - 200"
        )
        return (safe_headers(), flask.Response(
            json.dumps(response, ensure_ascii=False).encode("utf8"),
            mimetype="application/json; charset=utf-8",
            status=response['status'],
        ))

# Add this function after the visit_register decorator
def safe_headers():
    """Return a sanitized version of request headers with only safe headers."""
    safe_header_keys = {
        'User-Agent',
        'Accept',
        'Accept-Language',
        'Accept-Encoding',
        'Connection',
        'Host'
    }
    return {html.escape(k): html.escape(v) for k, v in flask.request.headers.items() if k in safe_header_keys}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
