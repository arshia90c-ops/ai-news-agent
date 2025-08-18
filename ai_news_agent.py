import os
import asyncio
import aiohttp
import feedparser
import requests
from bs4 import BeautifulSoup
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import time
import re
from urllib.parse import urljoin, urlparse

class AINewsAgent:
    def __init__(self):
        # API Keys from environment variables
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.email_password = os.getenv('EMAIL_APP_PASSWORD')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        # News sources
        self.website_sources = [
            ('https://feeds.feedburner.com/oreilly/radar', 'O\'Reilly Radar'),
            ('https://venturebeat.com/feed/', 'VentureBeat'),
            ('https://techcrunch.com/feed/', 'TechCrunch'),
            ('https://www.wired.com/feed/rss', 'Wired'),
            ('https://feeds.arstechnica.com/arstechnica/index', 'Ars Technica'),
            ('https://www.theverge.com/rss/index.xml', 'The Verge'),
            ('https://rss.cnn.com/rss/edition.rss', 'CNN'),
            ('https://feeds.bbci.co.uk/news/rss.xml', 'BBC News'),
            ('https://feeds.reuters.com/reuters/topNews', 'Reuters'),
            ('https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml', 'NY Times Tech'),
        ]
        
        self.reddit_sources = [
            'artificial',
            'MachineLearning', 
            'technology',
            'programming',
            'startups'
        ]
        
        # Initialize storage
        self.collected_articles = []
        self.analysis_results = []
        
    async def fetch_url(self, session, url, timeout=10):
        """Fetch URL with error handling"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    print(f"⚠️ HTTP {response.status} for {url}")
                    return None
        except Exception as e:
            print(f"❌ Error fetching {url}: {str(e)}")
            return None

    async def collect_rss_feeds(self):
        """Collect articles from RSS feeds"""
        print("📰 Collecting from RSS feeds...")
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for url, source_name in self.website_sources:
                tasks.append(self.process_rss_feed(session, url, source_name))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        articles_collected = sum(len(r) if isinstance(r, list) else 0 for r in results)
        print(f"✅ Collected {articles_collected} articles from RSS feeds")

    async def process_rss_feed(self, session, url, source_name):
        """Process a single RSS feed"""
        try:
            content = await self.fetch_url(session, url)
            if not content:
                return []
                
            feed = feedparser.parse(content)
            articles = []
            
            # Get articles from last 24 hours
            cutoff_time = datetime.now() - timedelta(days=1)
            
            for entry in feed.entries[:10]:  # Limit to 10 most recent
                try:
                    # Parse publication date
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = datetime(*entry.updated_parsed[:6])
                    
                    # Skip if too old
                    if pub_date and pub_date < cutoff_time:
                        continue
                    
                    # Extract article details
                    title = entry.get('title', 'No title')
                    link = entry.get('link', '')
                    
                    # Get description/summary
                    description = ''
                    if hasattr(entry, 'summary'):
                        description = BeautifulSoup(entry.summary, 'html.parser').get_text()
                    elif hasattr(entry, 'description'):
                        description = BeautifulSoup(entry.description, 'html.parser').get_text()
                    
                    # Clean and truncate description
                    description = re.sub(r'\s+', ' ', description).strip()
                    if len(description) > 500:
                        description = description[:500] + "..."
                    
                    article = {
                        'title': title,
                        'url': link,
                        'source': source_name,
                        'description': description,
                        'published': pub_date.isoformat() if pub_date else datetime.now().isoformat(),
                        'type': 'rss'
                    }
                    
                    articles.append(article)
                    
                except Exception as e:
                    print(f"⚠️ Error processing entry from {source_name}: {str(e)}")
                    continue
            
            self.collected_articles.extend(articles)
            return articles
            
        except Exception as e:
            print(f"❌ Error processing RSS feed {url}: {str(e)}")
            return []

    async def collect_reddit_posts(self):
        """Collect top posts from Reddit"""
        print("🔴 Collecting from Reddit...")
        
        async with aiohttp.ClientSession() as session:
            for subreddit in self.reddit_sources:
                try:
                    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=5"
                    content = await self.fetch_url(session, url)
                    
                    if content:
                        data = json.loads(content)
                        
                        for post in data['data']['children']:
                            post_data = post['data']
                            
                            # Skip if too old (last 24 hours)
                            post_time = datetime.fromtimestamp(post_data['created_utc'])
                            if post_time < datetime.now() - timedelta(days=1):
                                continue
                            
                            # Skip if score is too low
                            if post_data.get('score', 0) < 50:
                                continue
                            
                            article = {
                                'title': post_data['title'],
                                'url': f"https://reddit.com{post_data['permalink']}",
                                'source': f"r/{subreddit}",
                                'description': post_data.get('selftext', '')[:500] + "..." if post_data.get('selftext') else '',
                                'published': post_time.isoformat(),
                                'score': post_data.get('score', 0),
                                'type': 'reddit'
                            }
                            
                            self.collected_articles.append(article)
                            
                    await asyncio.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    print(f"⚠️ Error fetching r/{subreddit}: {str(e)}")
                    continue
        
        reddit_count = len([a for a in self.collected_articles if a['type'] == 'reddit'])
        print(f"✅ Collected {reddit_count} posts from Reddit")

    def analyze_with_gemini(self, articles_batch):
        """Analyze articles using Gemini API"""
        try:
            # Prepare articles for analysis
            articles_text = ""
            for i, article in enumerate(articles_batch):
                articles_text += f"\n\nArticle {i+1}:\nTitle: {article['title']}\nSource: {article['source']}\nDescription: {article['description'][:300]}..."
            
            prompt = f"""Analyze these news articles and provide a JSON response with the following structure for each article:

{{
  "articles": [
    {{
      "index": 1,
      "relevance_score": 85,
      "category": "AI/ML",
      "key_insights": ["insight1", "insight2"],
      "importance_level": "high",
      "summary": "Brief summary of the article"
    }}
  ]
}}

Categories to use: "AI/ML", "Technology", "Business", "Startups", "Programming", "Science", "Other"
Importance levels: "high", "medium", "low"
Relevance score: 0-100 based on current importance and interest

Articles to analyze:{articles_text}

Return only valid JSON, no additional text."""

            # Make API call to Gemini
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.gemini_api_key}"
            
            headers = {
                'Content-Type': 'application/json',
            }
            
            data = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }]
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract the generated text
                if 'candidates' in result and len(result['candidates']) > 0:
                    generated_text = result['candidates'][0]['content']['parts'][0]['text']
                    
                    # Clean up the response (remove markdown formatting)
                    generated_text = generated_text.replace('```json', '').replace('```', '').strip()
                    
                    # Parse JSON
                    try:
                        analysis = json.loads(generated_text)
                        return analysis.get('articles', [])
                    except json.JSONDecodeError as e:
                        print(f"⚠️ JSON parsing error: {str(e)}")
                        return []
                        
            else:
                print(f"❌ Gemini API error: {response.status_code}")
                print(response.text)
                return []
                
        except Exception as e:
            print(f"❌ Error in Gemini analysis: {str(e)}")
            return []

    async def analyze_articles(self):
        """Analyze all collected articles with AI"""
        if not self.collected_articles:
            print("⚠️ No articles to analyze")
            return
        
        print(f"🤖 Analyzing {len(self.collected_articles)} articles with AI...")
        
        # Process in batches to avoid token limits
        batch_size = 5
        all_analyses = []
        
        for i in range(0, len(self.collected_articles), batch_size):
            batch = self.collected_articles[i:i+batch_size]
            batch_analysis = self.analyze_with_gemini(batch)
            
            # Match analysis results with articles
            for j, analysis in enumerate(batch_analysis):
                if j < len(batch):
                    article_index = i + j
                    if article_index < len(self.collected_articles):
                        # Add analysis to the article
                        self.collected_articles[article_index].update({
                            'relevance_score': analysis.get('relevance_score', 50),
                            'category': analysis.get('category', 'Other'),
                            'key_insights': analysis.get('key_insights', []),
                            'importance_level': analysis.get('importance_level', 'medium'),
                            'ai_summary': analysis.get('summary', '')
                        })
            
            all_analyses.extend(batch_analysis)
            
            # Rate limiting
            if i + batch_size < len(self.collected_articles):
                await asyncio.sleep(2)
        
        # Sort articles by relevance score
        self.collected_articles.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        print(f"✅ Analysis complete. Average relevance: {sum(a.get('relevance_score', 0) for a in self.collected_articles) / len(self.collected_articles):.1f}")

    def generate_email_digest(self):
        """Generate HTML email digest"""
        if not self.collected_articles:
            return None
        
        # Filter articles by relevance (keep top stories)
        top_articles = [a for a in self.collected_articles if a.get('relevance_score', 0) >= 60][:15]
        
        if not top_articles:
            top_articles = self.collected_articles[:10]  # Fallback to top 10
        
        # Group by category
        categories = {}
        for article in top_articles:
            cat = article.get('category', 'Other')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(article)
        
        # Generate HTML
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 0 20px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
                .category {{ margin: 20px 0; }}
                .category-title {{ background: #f8f9fa; padding: 15px 20px; margin: 0; font-size: 18px; color: #333; border-left: 4px solid #667eea; }}
                .article {{ padding: 20px; border-bottom: 1px solid #eee; }}
                .article:last-child {{ border-bottom: none; }}
                .article-title {{ font-size: 16px; font-weight: bold; color: #333; margin-bottom: 8px; }}
                .article-title a {{ text-decoration: none; color: #333; }}
                .article-title a:hover {{ color: #667eea; }}
                .article-meta {{ font-size: 12px; color: #666; margin-bottom: 10px; }}
                .article-summary {{ color: #555; line-height: 1.5; margin-bottom: 10px; }}
                .insights {{ background: #f8f9fa; padding: 10px; border-radius: 5px; font-size: 14px; }}
                .insights strong {{ color: #667eea; }}
                .score {{ background: #667eea; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; float: right; }}
                .footer {{ text-align: center; padding: 20px; background: #f8f9fa; color: #666; font-size: 14px; }}
                .stats {{ background: #f8f9fa; padding: 15px 20px; display: flex; justify-content: space-around; }}
                .stat {{ text-align: center; }}
                .stat-number {{ font-size: 24px; font-weight: bold; color: #667eea; }}
                .stat-label {{ font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤖 AI News Intelligence</h1>
                    <p>Daily Digest - {datetime.now().strftime('%A, %B %d, %Y')}</p>
                </div>
                
                <div class="stats">
                    <div class="stat">
                        <div class="stat-number">{len(top_articles)}</div>
                        <div class="stat-label">Articles</div>
                    </div>
                    <div class="stat">
                        <div class="stat-number">{len(categories)}</div>
                        <div class="stat-label">Categories</div>
                    </div>
                    <div class="stat">
                        <div class="stat-number">{len(set(a['source'] for a in top_articles))}</div>
                        <div class="stat-label">Sources</div>
                    </div>
                    <div class="stat">
                        <div class="stat-number">{sum(a.get('relevance_score', 0) for a in top_articles) // len(top_articles) if top_articles else 0}</div>
                        <div class="stat-label">Avg Score</div>
                    </div>
                </div>
        """
        
        # Add categories and articles
        for category, articles in categories.items():
            html_content += f"""
                <div class="category">
                    <h2 class="category-title">{category} ({len(articles)} articles)</h2>
            """
            
            for article in articles:
                insights_html = ""
                if article.get('key_insights'):
                    insights = ", ".join(article['key_insights'][:3])  # Limit to 3 insights
                    insights_html = f'<div class="insights"><strong>Key insights:</strong> {insights}</div>'
                
                html_content += f"""
                    <div class="article">
                        <div class="article-title">
                            <a href="{article['url']}" target="_blank">{article['title']}</a>
                            <span class="score">{article.get('relevance_score', 'N/A')}</span>
                        </div>
                        <div class="article-meta">
                            {article['source']} • {article.get('importance_level', 'medium').title()} priority • {datetime.fromisoformat(article['published'].replace('Z', '+00:00')).strftime('%I:%M %p') if 'T' in article['published'] else 'Recent'}
                        </div>
                        <div class="article-summary">{article.get('ai_summary') or article['description']}</div>
                        {insights_html}
                    </div>
                """
            
            html_content += "</div>"
        
        html_content += """
                <div class="footer">
                    <p>Powered by AI News Intelligence Agent 🤖</p>
                    <p>This digest was generated automatically using AI analysis</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content

    def send_email(self, html_content):
        """Send email digest"""
        try:
            print("📧 Sending email digest...")
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"AI News Digest - {datetime.now().strftime('%B %d, %Y')}"
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.sender_email, self.email_password)
                server.send_message(msg)
            
            print("✅ Email sent successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error sending email: {str(e)}")
            return False

    def save_data_for_dashboard(self):
        """Save collected data for dashboard"""
        try:
            print("💾 Saving data for dashboard...")
            
            # Create data directory structure
            os.makedirs('data', exist_ok=True)
            
            # Save articles data
            timestamp = datetime.now().strftime('%Y%m%d')
            
            # Daily data
            daily_data = {
                'date': datetime.now().isoformat(),
                'articles': self.collected_articles,
                'summary': {
                    'total_articles': len(self.collected_articles),
                    'avg_relevance': sum(a.get('relevance_score', 0) for a in self.collected_articles) / len(self.collected_articles) if self.collected_articles else 0,
                    'categories': list(set(a.get('category', 'Other') for a in self.collected_articles)),
                    'sources': list(set(a.get('source', '') for a in self.collected_articles))
                }
            }
            
            # Save daily data
            with open(f'data/articles_{timestamp}.json', 'w') as f:
                json.dump(daily_data, f, indent=2)
            
            # Update latest data for dashboard
            with open('data/latest.json', 'w') as f:
                json.dump(daily_data, f, indent=2)
            
            print(f"✅ Data saved: {len(self.collected_articles)} articles")
            
        except Exception as e:
            print(f"❌ Error saving data: {str(e)}")

    async def run_daily_digest(self):
        """Run the complete daily news digest process"""
        print("🚀 Starting AI News Agent - Daily Digest")
        print(f"📅 {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
        print("-" * 50)
        
        try:
            # Step 1: Collect articles
            await self.collect_rss_feeds()
            await self.collect_reddit_posts()
            
            if not self.collected_articles:
                print("⚠️ No articles collected. Ending process.")
                return
            
            print(f"📊 Total articles collected: {len(self.collected_articles)}")
            
            # Step 2: AI Analysis
            await self.analyze_articles()
            
            # Step 3: Generate and send email
            html_digest = self.generate_email_digest()
            if html_digest:
                self.send_email(html_digest)
            
            # Step 4: Save data for dashboard
            self.save_data_for_dashboard()
            
            print("-" * 50)
            print("✅ Daily digest process completed successfully!")
            
        except Exception as e:
            print(f"❌ Error in daily digest process: {str(e)}")
            raise

# Main execution
async def main():
    mode = os.getenv('AGENT_MODE', 'daily')
    
    agent = AINewsAgent()
    
    if mode == 'daily':
        await agent.run_daily_digest()
    else:
        print(f"Unknown mode: {mode}")

if __name__ == "__main__":
    asyncio.run(main())
