# BBC News API for Geox App

A Flask-based API that provides BBC news articles with real images, designed as a drop-in replacement for Google News RSS feeds.

## 🚀 Features

- ✅ **Fresh BBC News**: Direct from BBC sources (not delayed like Google News)
- ✅ **Real Article Images**: Extracts actual images from BBC articles (no generic icons)
- ✅ **GNews Compatible**: Same API interface as Google News RSS
- ✅ **Caching**: Built-in image and URL caching for performance
- ✅ **Cloud Ready**: Optimized for deployment on LeapCell, Vercel, or any Python hosting

## 📁 Files Structure

```
bbc-api/
├── main.py              # Flask application
├── requirements.txt     # Python dependencies
├── vercel.json         # Deployment configuration
├── .gitignore          # Git ignore rules
├── LICENSE             # MIT License
└── README.md           # This file
```

## 🛠️ API Endpoints

### GET /news

Fetch BBC news articles with real images.

**Query Parameters:**
- `q` (optional): Search query
- `topic` (optional): News topic (WORLD, BUSINESS, etc.)
- `country` (optional): Country code (default: IN)
- `language` (optional): Language code (default: en)
- `max_results` (optional): Maximum articles to return (default: 10)

**Example Request:**
```
GET /news?max_results=5&topic=WORLD
```

**Response Format:**
```json
{
  "articles": [
    {
      "title": "Article Title",
      "description": "Article summary...",
      "url": "https://www.bbc.com/news/article-url",
      "urlToImage": "https://real-article-image.jpg",
      "publishedAt": "2025-01-17T10:30:00Z",
      "author": "BBC News",
      "source": "BBC News",
      "category": "general",
      "region": "IN",
      "tags": [],
      "readTime": 3,
      "aiSummary": ""
    }
  ]
}
```

## 🚀 Deployment Options

### Option 1: LeapCell (Recommended)

1. **Create GitHub Repository:**
   - Go to GitHub.com → New Repository
   - Name: `bbc-news-api` or `geox-bbc-api`
   - Upload all files from this folder

2. **Deploy on LeapCell:**
   - Go to [leapcell.io](https://leapcell.io)
   - Connect your GitHub account
   - Select your `bbc-news-api` repository
   - Deploy automatically

3. **Get Deployment URL:**
   - After deployment: `https://your-project.leapcell.io`

### Option 2: Vercel

1. **Import to Vercel:**
   - Go to [vercel.com](https://vercel.com)
   - Import GitHub repository
   - Vercel auto-detects Python/Flask
   - Deploy

### Option 3: Manual Upload

Upload files directly to your hosting provider.

## 🧪 Testing

After deployment, test with:

```bash
curl "https://your-api-url/news?max_results=3"
```

Expected: JSON response with 3 BBC articles, each with real images.

## 🔧 Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py

# Test API
curl "http://localhost:5000/news?max_results=2"
```

## 📱 Integration with Flutter App

Update your Flutter news service to use the BBC API URL:

```dart
// Replace GNews URL with BBC API URL
const String apiUrl = 'https://your-bbc-api.leapcell.io/news';
```

## 🏗️ Architecture

- **URL Resolution**: Converts Google-style URLs to real BBC article URLs
- **Image Extraction**: Scrapes `og:image` meta tags from actual articles
- **Caching**: Prevents repeated API calls and scraping
- **Error Handling**: Graceful fallbacks when images aren't available

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to GitHub
5. Create Pull Request

---

**Built for Geox App** - Real news, real images, real fast.
