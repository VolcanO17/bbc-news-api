from flask import Flask, request, jsonify, render_template, send_from_directory, Response
import requests
import time
import json
import logging
import pytz
from datetime import datetime
import random
import functools
import os
import dotenv
import html
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import sys
sys.path.insert(0, 'C:\\Users\\VolcanO\\AppData\\Local\\Programs\\Python\\Python313\\Lib\\site-packages')
import bbc

dotenv.load_dotenv()

# ================ LOGGING INITIATION ================
logger = logging.getLogger('BBC-API')
logger.setLevel(logging.INFO)

# Simple console logging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ================ FLASK INITIATION ================
app = Flask(__name__, static_folder="templates", static_url_path="/static")

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

# Remove complex async decorators that might cause issues

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

# Simplified BBC scraping function
def _get(lang, latest):
    start = time.time()
    response = {}
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        r = requests.get(lang, headers=headers, timeout=10)
        response["status"] = r.status_code

        if r.status_code == 200:
            soup = BeautifulSoup(r.content, 'html.parser')
            sections = soup.find_all('section', {'aria-labelledby': True})

            for section in sections:
                title_elem = section.find("h2")
                if not title_elem:
                    continue

                title = title_elem.get_text().strip()
                section_news = []

                # Find news items in this section
                news_items = section.find_all('li')
                for item in news_items[:5]:  # Limit to 5 per section
                    title_link = item.find('h3 a')
                    if not title_link:
                        continue

                    news_title = title_link.get_text().strip()
                    news_link = title_link.get('href')
                    if news_link and not news_link.startswith('http'):
                        news_link = urljoin(lang, news_link)

                    summary_elem = item.find('p')
                    news_summary = summary_elem.get_text().strip() if summary_elem else ""

                    img_elem = item.find('img')
                    image_link = img_elem.get('src') if img_elem else ""

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

def scrape_bbc_section(url, max_results=10):
    """Scrape articles from a BBC section URL"""
    print(f"Scraping BBC section: {url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []

        # Determine the URL pattern based on the section URL
        if '/sport' in url:
            url_pattern = lambda x: x and '/sport/' in x and len(x) > 20 and any(char.isdigit() for char in x)
        elif '/news/technology' in url:
            url_pattern = lambda x: x and ('/news/technology/' in x or '/news/articles/' in x) and len(x) > 20
        elif '/news/science' in url:
            url_pattern = lambda x: x and ('/news/science' in x or '/news/articles/' in x) and len(x) > 20
        elif '/news/business' in url:
            url_pattern = lambda x: x and ('/news/business/' in x or '/news/articles/' in x) and len(x) > 20
        elif '/news/politics' in url:
            url_pattern = lambda x: x and ('/news/politics/' in x or '/news/articles/' in x) and len(x) > 20
        elif '/news/world' in url:
            url_pattern = lambda x: x and ('/news/world/' in x or '/news/articles/' in x) and len(x) > 20
        elif '/news/health' in url:
            url_pattern = lambda x: x and ('/news/health/' in x or '/news/articles/' in x) and len(x) > 20
        elif '/news/entertainment' in url:
            url_pattern = lambda x: x and ('/news/entertainment' in x or '/news/articles/' in x) and len(x) > 20
        else:
            # Fallback for other sections
            url_pattern = lambda x: x and ('/news/articles/' in x or '/sport/' in x) and len(x) > 20

        # Find actual article links based on the section
        article_links = soup.find_all('a', href=url_pattern)

        # If no specific pattern matches, try a broader approach
        if not article_links:
            article_links = soup.find_all('a', href=lambda x: x and len(x) > 30 and ('/news/' in x or '/sport/' in x) and any(char.isdigit() for char in x))

        seen_titles = set()
        for link in article_links:
            if len(articles) >= max_results:
                break

            href = link.get('href')
            text = link.get_text().strip()

            # Look for title in various places
            title = ''

            # Check if the link itself has text
            if text and len(text) > 10:
                title = text
            else:
                # Look in parent elements for title
                parent = link.parent
                for _ in range(3):  # Check up to 3 levels up
                    if parent:
                        h3 = parent.find('h3')
                        if h3:
                            title = h3.get_text().strip()
                            break
                        span = parent.find('span')
                        if span and len(span.get_text().strip()) > 10:
                            title = span.get_text().strip()
                            break
                        p = parent.find('p')
                        if p and len(p.get_text().strip()) > 10:
                            title = p.get_text().strip()
                            break
                    parent = parent.parent if parent else None

            # Skip if title is too short, already seen, or is a section header
            if not title or len(title) <= 15 or title in seen_titles:
                continue

            # Skip section headers and navigation
            if any(skip in title.lower() for skip in ['video', 'more', 'also in', 'only from', 'insight', 'live', 'watch', 'listen']):
                continue

            seen_titles.add(title)

            # Get full URL
            if href.startswith('/'):
                full_url = f"https://www.bbc.com{href}"
            else:
                full_url = href

            # Look for summary in nearby elements
            summary = ""
            parent = link.parent
            if parent:
                p_elem = parent.find('p')
                if p_elem:
                    summary = p_elem.get_text().strip()

            # Look for image in parent container
            image_src = ""
            if parent:
                img_elem = parent.find('img')
                if img_elem:
                    if 'srcset' in img_elem.attrs and img_elem.attrs['srcset']:
                        image_src = img_elem.attrs['srcset'].split(',')[0].split(' ')[0]
                    else:
                        image_src = img_elem.attrs.get('src', "")

            articles.append({
                "title": title,
                "summary": summary,
                "image": image_src,
                "link": full_url
            })

        print(f"Found {len(articles)} articles for {url}")
        return articles

    except Exception as e:
        print(f"Error scraping BBC section {url}: {e}")
        return []

def get_eng(bbc_url='https://www.bbc.com/', latest=False):
    response = {}
    start = time.time()
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        r = requests.get(bbc_url, headers=headers, timeout=10)

        if r.status_code != 200:
            response["status"] = 503
            response["error"] = f"Failed to retrieve content. BBC website returned status code: {r.status_code}"
            return response

        soup = BeautifulSoup(r.content, 'html.parser')
        response["status"] = r.status_code

        # Find all sections
        sections = soup.find_all(['section', 'div'], {'data-testid': lambda x: x and x.endswith('-section')})

        for section in sections:
            # Get section title
            title_elem = section.find(['h2', 'div'], {'data-testid': lambda x: x and x.endswith('-title-wrapper')})
            if title_elem:
                title_elem = title_elem.find('h2') if title_elem.name != 'h2' else title_elem
                title_text = title_elem.get_text().strip() if title_elem else "Latest"
            else:
                title_text = "Latest"

            sec_news = []

            # Find all news cards in this section
            cards = section.find_all('div', {'data-testid': lambda x: x and x.endswith('-card')})

            for card in cards[:8]:  # Limit to 8 per section
                # Extract title
                heading_elem = card.find('h2', {'data-testid': 'card-headline'})
                heading_text = heading_elem.get_text().strip() if heading_elem else ""

                # Extract summary
                summary_elem = card.find('p', {'data-testid': 'card-description'})
                summary_text = summary_elem.get_text().strip() if summary_elem else ""

                # Extract image
                img_elem = card.find('img')
                image_src = ""
                if img_elem:
                    if 'srcset' in img_elem.attrs and img_elem.attrs['srcset']:
                        image_src = img_elem.attrs['srcset'].split(',')[0].split(' ')[0]
                    else:
                        image_src = img_elem.attrs.get('src', "")

                # Extract link
                link_elem = card.find('a')
                news_link = ""
                if link_elem and link_elem.get('href'):
                    href = link_elem.get('href')
                    if href.startswith('/'):
                        news_link = f"https://www.bbc.com{href}"
                    else:
                        news_link = href

                if heading_text:  # Only add if we have a title
                    sec_news.append({
                        "title": heading_text,
                        "summary": summary_text,
                        "image_link": image_src,
                        "news_link": news_link
                    })

            if sec_news:
                response[title_text] = sec_news

            if latest:
                break

        # Filter out empty sections
        response = {k: v for k, v in response.items() if v}

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
def ping():
    logger.info("Ping endpoint called - 200")
    return jsonify({"status": 200})

@app.route("/doc")
@app.route("/doc/")
@app.route("/docs")
@app.route("/docs/")
@app.route("/documentation")
@app.route("/documentation/")
def doc():
    lang = random.choice(list(urls.keys()))
    logger.info("DOC endpoint called - 200")
    return render_template("documentation.html",
                          listOfLangs="\n".join([f"<li>{key.capitalize()}: <code>{key}</code></li>" for key in sorted(urls.keys())]),
                          type="{type}",
                          language="{language}",
                          lang=lang.title(),
                          urlForNews=f"https://{request.url.split('/')[2]}/news?lang={lang}",
                          urlForLatest=f"https://{request.url.split('/')[2]}/latest?lang={lang}",
                          currentYear=str(datetime.now(pytz.timezone("Asia/Dhaka")).year))

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
        topic = request.args.get('topic', '').lower()
        country = request.args.get('country', 'GB')  # Default to GB for BBC
        language = request.args.get('language', 'en')
        max_results = int(request.args.get('max_results', 10))

        # Use direct BBC scraping for category-based news to ensure proper categorization
        if topic and topic != 'general':
            # Map topic to specific BBC section URLs for accurate categorization
            url_mapping = {
                'technology': 'https://www.bbc.com/news/technology',
                'science': 'https://www.bbc.com/news/science_and_environment',
                'business': 'https://www.bbc.com/news/business',
                'politics': 'https://www.bbc.com/news/politics',
                'world': 'https://www.bbc.com/news/world',
                'health': 'https://www.bbc.com/news/health',
                'entertainment': 'https://www.bbc.com/news/entertainment_and_arts',
                'sports': 'https://www.bbc.com/sport',
                'geopolitics': 'https://www.bbc.com/news/world',
                'stock_market': 'https://www.bbc.com/news/business',
                'food': 'https://www.bbc.com/news/world',
                'defense': 'https://www.bbc.com/news/world',
            }

            section_url = url_mapping.get(topic, 'https://www.bbc.com/news')

            print(f"Topic: {topic}, URL: {section_url}")
            try:
                # Scrape the specific BBC section
                section_data = scrape_bbc_section(section_url, max_results)
                print(f"Section articles scraped: {len(section_data)}")

                # Transform to GNews format
                articles = []
                for article_data in section_data:
                    article = {
                        'title': article_data.get('title', ''),
                        'description': article_data.get('summary', ''),
                        'url': article_data.get('link', ''),
                        'urlToImage': get_article_image(article_data.get('link', '')),
                        'publishedAt': datetime.now(pytz.timezone("Asia/Dhaka")).strftime('%Y-%m-%dT%H:%M:%SZ'),
                        'author': 'BBC News',
                        'source': 'BBC News',
                        'category': topic,
                        'region': 'global',
                        'tags': [topic.lower()],
                        'readTime': len(article_data.get('summary') or '') // 200 + 1,
                        'aiSummary': ''
                    }

                    # Apply query filter if specified
                    if query:
                        search_text = (article['title'] + ' ' + article['description']).lower()
                        if query.lower() not in search_text:
                            continue

                    articles.append(article)

                print(f"Articles created: {len(articles)}")
                if articles:
                    return jsonify({'articles': articles})

            except Exception as scrape_e:
                print(f"Scraping failed for topic {topic}: {scrape_e}, falling back to general scraping")

        # Fallback: For general or unknown topics, use the existing scraping method
        bbc_data = get_eng(False)  # Get all sections

        if bbc_data.get('status') != 200:
            return jsonify({'error': 'Failed to fetch BBC news'}), 500

        # Transform BBC data to GNews format
        articles = transform_bbc_to_gnews_format(bbc_data, query, topic, max_results)

        if not articles:
            return jsonify({'error': 'No articles found'}), 404

        return jsonify({'articles': articles})

        # Fallback: For general or unknown topics, use the existing scraping method
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

    # Filter out non-section keys
    relevant_sections = [s for s in bbc_data.keys() if isinstance(bbc_data[s], list)]

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

# Remove log endpoints that require PIN and file access

# Serve static files for index page
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

@app.route("/languages")
def languages():
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
    return jsonify(response)

# Remove legacy endpoints for simplicity

# Remove unused functions

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
