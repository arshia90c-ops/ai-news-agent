#!/usr/bin/env python3
"""
AI News Intelligence Agent
Collects, analyzes, and delivers personalized news digests
"""

import os
import sys
import json
import asyncio
import aiohttp
import feedparser
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import ssl
from bs4 import BeautifulSoup
import google.generativeai as genai
from typing import List, Dict, Any
import re
import time

class AINewsAgent:
    def __init__(self):
        # API Configuration
        self.gemini_api_key = os.environ.get('GEMINI_API_KEY')
        self.sender_email = os.environ.get('SENDER_EMAIL')
        self.email_password = os.environ.get('EMAIL_APP_PASSWORD')
        self.recipient_email = os.environ.get('RECIPIENT_EMAIL')
        
        if not all([self.gemini_api_key, self.sender_email, self.email_password, self.recipient_email]):
            raise ValueError("Missing required environment variables")
        
        # Configure Gemini
        genai.configure(api_key=self.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        # News sources
        self.website_sources = [
            ('https://feeds.feedburner.com/oreilly/radar', 'O\'Reilly Radar'),
            ('https://feeds.feedburner.com/venturebeat/SZYF', 'VentureBeat'),
            ('https://techcrunch.com/feed/', 'TechCrunch'),
            ('https://www.wired.com/feed/rss', 'WIRED'),
            ('https://feeds.arstechnica.com/arstechnica/index', 'Ars Technica'),
            ('https://rss.cnn.com/rss/edition.rss', 'CNN'),
            ('https://feeds.bbci.co.uk/news/rss.xml', 'BBC News'),
            ('https://www.theverge.com/rss/index.xml', 'The Verge'),
            ('https://feeds.reuters.com/reuters/technologyNews', 'Reuters Tech'),
            ('https://www.reddit.com/r/MachineLearning/.rss', 'Reddit ML'),
            ('https://www.reddit.com/r/artificial/.rss', 'Reddit AI'),
            ('https://www.reddit.com/r/technology/.rss', 'Reddit Tech'),
        ]
        
        self.collected_articles = []
        
    async def collect_from_websites(self) -> List[Dict[str, Any]]:
        """Collect articles from RSS feeds"""
        articles = []
        
        async with aiohttp.ClientSession() as session:
            for url, source_name in self.website_sources:
                try:
                    print(f"📰 Collecting from {source_name}...")
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            content = await response.text()
                            feed = feedparser.parse(content)
                            
                            for entry in feed.entries[:5]:  # Limit to 5 articles per source
                                article = {
                                    'title': entry.get('title', 'No title'),
                                    'url': entry.get('link', ''),
                                    'description': self.clean_text(entry.get('summary', entry.get('description', ''))),
                                    'published': self.parse_date(entry.get('published', '')),
                                    'source': source_name,
                                    'content_type': 'website'
                                }
                                articles.append(article)
                                
                except Exception as e:
                    print(f"❌ Error collecting from {source_name}: {str(e)}")
                    continue
                    
                # Rate limiting
                await asyncio.sleep(0.5)
        
        return articles
    
    def collect_social_media(self) -> List[Dict[str, Any]]:
        """Collect from social media sources"""
        articles = []
        
        # Reddit posts (using RSS - no API key needed)
        reddit_sources = [
            ('https://www.reddit.com/r/MachineLearning/top/.rss?t=day', 'Reddit ML'),
            ('https://www.reddit.com/r/artificial/top/.rss?t=day', 'Reddit AI'),
            ('https://www.reddit.com/r/programming/top/.rss?t=day', 'Reddit Programming'),
        ]
        
        for url, source_name in reddit_sources:
            try:
                print(f"🔥 Collecting trending from {source_name}...")
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)
                    
                    for entry in feed.entries[:3]:  # Top 3 posts
                        article = {
                            'title': entry.get('title', 'No title'),
                            'url': entry.get('link', ''),
                            'description': self.clean_text(entry.get('summary', '')),
                            'published': self.parse_date(entry.get('published', '')),
                            'source': source_name,
                            'content_type': 'social'
                        }
                        articles.append(article)
                        
            except Exception as e:
                print(f"❌ Error collecting from {source_name}: {str(e)}")
                continue
                
            time.sleep(1)  # Rate limiting
        
        return articles
    
    def clean_text(self, text: str) -> str:
        """Clean and format text content"""
        if not text:
            return ""
        
        # Remove HTML tags
        soup = BeautifulSoup(text, 'html.parser')
        text = soup.get_text()
        
        # Clean up whitespace and special characters
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        
        return text.strip()[:500]  # Limit length
    
    def parse_date(self, date_str: str) -> str:
        """Parse various date formats"""
        if not date_str:
            return datetime.now().isoformat()
        
        try:
            # Try common formats
            for fmt in ['%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S']:
                try:
                    return datetime.strptime(date_str, fmt).isoformat()
                except:
                    continue
            
            # Fallback
            return datetime.now().isoformat()
        except:
            return datetime.now().isoformat()
    
    def analyze_with_ai(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze articles with Gemini AI"""
        if not articles:
            return {"analysis": "No articles to analyze", "categorized_articles": []}
        
        try:
            # Prepare articles for AI analysis
            articles_text = "\n\n".join([
                f"Title: {article['title']}\n"
                f"Source: {article['source']}\n"
                f"Description: {article['description'][:300]}..."
                for article in articles[:20]  # Limit for API
            ])
            
            prompt = f"""
            Analyze these news articles and provide:
            1. A brief summary of key trends and themes
            2. Rate each article's importance (1-10)
            3. Categorize articles (Technology, AI/ML, Business, Science, Other)
            4. Identify the top 5 most important stories
            5. Note any emerging patterns or connections between stories
            
            Articles:
            {articles_text}
            
            Provide response in this JSON format:
            {{
                "summary": "Brief analysis of key trends and themes",
                "top_stories": ["title1", "title2", "title3", "title4", "title5"],
                "categories": {{
                    "Technology": ["title1", "title2"],
                    "AI/ML": ["title1", "title2"],
                    "Business": ["title1"],
                    "Science": ["title1"],
                    "Other": ["title1"]
                }},
                "insights": "Key insights and patterns observed",
                "market_sentiment": "positive/negative/neutral with brief explanation"
            }}
            """
            
            response = self.model.generate_content(prompt)
            
            # Try to parse JSON response
            try:
                analysis = json.loads(response.text)
            except:
                # Fallback if JSON parsing fails
                analysis = {
                    "summary": response.text[:500],
                    "top_stories": [article['title'] for article in articles[:5]],
                    "categories": {"Other": [article['title'] for article in articles[:10]]},
                    "insights": "Analysis completed",
                    "market_sentiment": "neutral - automated analysis"
                }
            
            return analysis
            
        except Exception as e:
            print(f"❌ AI Analysis error: {str(e)}")
            return {
                "summary": "AI analysis temporarily unavailable",
                "top_stories": [article['title'] for article in articles[:5]],
                "categories": {"Other": [article['title'] for article in articles[:10]]},
                "insights": "Manual review recommended",
                "market_sentiment": "neutral - analysis unavailable"
            }
    
    def generate_email_content(self, articles: List[Dict[str, Any]], analysis: Dict[str, Any], mode: str = 'daily') -> str:
        """Generate HTML email content"""
        now = datetime.now()
        
        if mode == 'weekly':
            title = f"🔍 Weekly AI News Intelligence - Week of {now.strftime('%B %d, %Y')}"
            subtitle = "Your Weekly Technology & AI Digest"
        else:
            title = f"🔍 Daily AI News Intelligence - {now.strftime('%B %d, %Y')}"
            subtitle = "Your Daily Technology & AI Digest"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f8f9fa; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; }}
                .header p {{ margin: 10px 0 0; opacity: 0.9; }}
                .summary {{ background: white; padding: 25px; border-radius: 8px; margin-bottom: 25px; border-left: 4px solid #667eea; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .summary h2 {{ color: #667eea; margin-top: 0; }}
                .category {{ background: white; margin-bottom: 25px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .category-header {{ background: #f8f9fa; padding: 15px 25px; border-bottom: 1px solid #e9ecef; }}
                .category-header h3 {{ margin: 0; color: #495057; }}
                .article {{ padding: 20px 25px; border-bottom: 1px solid #f1f3f4; }}
                .article:last-child {{ border-bottom: none; }}
                .article h4 {{ margin: 0 0 10px; color: #212529; }}
                .article h4 a {{ color: #667eea; text-decoration: none; }}
                .article h4 a:hover {{ text-decoration: underline; }}
                .article p {{ margin: 5px 0; color: #6c757d; font-size: 14px; }}
                .article .meta {{ font-size: 12px; color: #adb5bd; margin-top: 10px; }}
                .insights {{ background: #e8f4f8; padding: 20px; border-radius: 8px; margin-top: 25px; }}
                .insights h3 {{ color: #0c4a6e; margin-top: 0; }}
                .footer {{ text-align: center; margin-top: 40px; padding: 20px; color: #6c757d; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{title}</h1>
                <p>{subtitle}</p>
                <p>Powered by AI • Generated on {now.strftime('%A, %B %d, %Y at %I:%M %p UTC')}</p>
            </div>
            
            <div class="summary">
                <h2>🔍 AI Analysis Summary</h2>
                <p><strong>Key Trends:</strong> {analysis.get('summary', 'No analysis available')}</p>
                <p><strong>Market Sentiment:</strong> {analysis.get('market_sentiment', 'Neutral')}</p>
                <p><strong>Articles Analyzed:</strong> {len(articles)} sources</p>
            </div>
        """
        
        # Add categorized articles
        categories = analysis.get('categories', {})
        if not categories:
            # Fallback categorization
            categories = {"All Stories": [article['title'] for article in articles[:15]]}
        
        for category, titles in categories.items():
            if not titles:
                continue
                
            category_articles = [article for article in articles if article['title'] in titles]
            if not category_articles:
                continue
                
            html_content += f"""
            <div class="category">
                <div class="category-header">
                    <h3>📂 {category}</h3>
                </div>
            """
            
            for article in category_articles[:5]:  # Limit per category
                html_content += f"""
                <div class="article">
                    <h4><a href="{article['url']}" target="_blank">{article['title']}</a></h4>
                    <p>{article['description'][:200]}...</p>
                    <div class="meta">
                        <span>📍 {article['source']}</span> • 
                        <span>🕒 {datetime.fromisoformat(article['published']).strftime('%B %d, %Y')}</span>
                    </div>
                </div>
                """
            
            html_content += "</div>"
        
        # Add insights
        html_content += f"""
            <div class="insights">
                <h3>💡 Key Insights</h3>
                <p>{analysis.get('insights', 'Continue monitoring for emerging trends and patterns.')}</p>
            </div>
            
            <div class="footer">
                <p>🤖 Generated by AI News Intelligence Agent</p>
                <p>This digest analyzed {len(articles)} articles from {len(set(article['source'] for article in articles))} sources</p>
                <p><a href="https://arshia90c-ops.github.io/ai-news-agent" style="color: #667eea;">View Live Dashboard</a></p>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def send_email(self, subject: str, html_content: str):
        """Send email digest"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(self.sender_email, self.email_password)
                server.sendmail(self.sender_email, self.recipient_email, msg.as_string())
            
            print("✅ Email sent successfully!")
            
        except Exception as e:
            print(f"❌ Email error: {str(e)}")
            raise
    
    def save_data(self, articles: List[Dict[str, Any]], analysis: Dict[str, Any], mode: str):
        """Save data for dashboard and analysis"""
        timestamp = datetime.now().isoformat()
        
        # Create data directory
        os.makedirs('data', exist_ok=True)
        
        # Save daily data
        daily_file = f"data/{datetime.now().strftime('%Y-%m-%d')}.json"
        daily_data = {
            'timestamp': timestamp,
            'mode': mode,
            'articles': articles,
            'analysis': analysis,
            'stats': {
                'total_articles': len(articles),
                'sources_count': len(set(article['source'] for article in articles)),
                'categories': list(analysis.get('categories', {}).keys())
            }
        }
        
        with open(daily_file, 'w') as f:
            json.dump(daily_data, f, indent=2)
        
        print(f"💾 Data saved to {daily_file}")
    
    async def run(self, mode: str = 'daily'):
        """Main execution function"""
        print(f"🚀 Starting AI News Agent in {mode} mode...")
        
        try:
            # Collect articles
            print("📰 Collecting from websites...")
            website_articles = await self.collect_from_websites()
            
            print("🔥 Collecting from social media...")
            social_articles = self.collect_social_media()
            
            # Combine all articles
            all_articles = website_articles + social_articles
            print(f"📊 Collected {len(all_articles)} articles total")
            
            if not all_articles:
                print("⚠️  No articles collected, exiting...")
                return
            
            # AI Analysis
            print("🤖 Running AI analysis...")
            analysis = self.analyze_with_ai(all_articles)
            
            # Generate email
            print("📧 Generating email content...")
            subject = f"🔍 {mode.title()} AI News Intelligence - {datetime.now().strftime('%B %d, %Y')}"
            html_content = self.generate_email_content(all_articles, analysis, mode)
            
            # Send email
            print("📤 Sending email digest...")
            self.send_email(subject, html_content)
            
            # Save data
            print("💾 Saving data...")
            self.save_data(all_articles, analysis, mode)
            
            print("✅ AI News Agent completed successfully!")
            
        except Exception as e:
            print(f"❌ Error in main execution: {str(e)}")
            raise

def main():
    """Main entry point"""
    mode = sys.argv[1] if len(sys.argv) > 1 else 'daily'
    
    if mode not in ['daily', 'weekly']:
        print("❌ Invalid mode. Use 'daily' or 'weekly'")
        sys.exit(1)
    
    agent = AINewsAgent()
    asyncio.run(agent.run(mode))

if __name__ == "__main__":
    main()
