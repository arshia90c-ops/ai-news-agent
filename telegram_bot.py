import asyncio
import aiohttp
import feedparser
import json
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import os
import requests
from bs4 import BeautifulSoup
import re

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AINewsTelegramBot:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.news_sources = [
            ('https://feeds.feedburner.com/oreilly/radar', 'O\'Reilly Radar'),
            ('https://feeds.macrumors.com/MacRumors-All', 'MacRumors'),
            ('https://feeds.feedburner.com/venturebeat/SZYF', 'VentureBeat'),
            ('https://rss.cnn.com/rss/edition.rss', 'CNN'),
            ('https://feeds.bbci.co.uk/news/rss.xml', 'BBC News'),
            ('https://techcrunch.com/feed/', 'TechCrunch'),
            ('https://www.wired.com/feed/rss', 'WIRED'),
            ('https://feeds.reuters.com/reuters/technologyNews', 'Reuters Tech'),
        ]
        self.articles_cache = []
        self.last_update = None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        welcome_message = """
🤖 **AI News Intelligence Bot**

Welcome! I'm your personal AI news assistant. Here's what I can do:

📰 **/latest** - Get latest news digest
📊 **/categories** - Browse by categories  
🔍 **/search [keyword]** - Search specific topics
📈 **/trending** - Show trending stories
⚙️ **/settings** - Configure preferences
ℹ️ **/help** - Show all commands

Let's get started! Try /latest to see today's top stories.
        """
        
        keyboard = [
            [InlineKeyboardButton("📰 Latest News", callback_data='latest')],
            [InlineKeyboardButton("📊 Categories", callback_data='categories')],
            [InlineKeyboardButton("📈 Trending", callback_data='trending')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_message, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )

    async def collect_news(self):
        """Collect news from all sources"""
        logger.info("🔄 Collecting news from sources...")
        articles = []
        
        async with aiohttp.ClientSession() as session:
            for url, source in self.news_sources:
                try:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            content = await response.text()
                            feed = feedparser.parse(content)
                            
                            for entry in feed.entries[:5]:  # Top 5 from each source
                                article = {
                                    'title': entry.get('title', 'No title'),
                                    'link': entry.get('link', ''),
                                    'summary': entry.get('summary', '')[:300] + '...',
                                    'published': entry.get('published', ''),
                                    'source': source,
                                    'timestamp': datetime.now().isoformat()
                                }
                                articles.append(article)
                                
                except Exception as e:
                    logger.error(f"Error fetching from {source}: {e}")
                    continue
        
        # Analyze articles with AI
        analyzed_articles = await self.analyze_articles_with_ai(articles)
        self.articles_cache = analyzed_articles
        self.last_update = datetime.now()
        
        return analyzed_articles

    async def analyze_articles_with_ai(self, articles):
        """Analyze articles using Gemini AI"""
        if not self.gemini_api_key:
            logger.warning("No Gemini API key found, skipping AI analysis")
            for article in articles:
                article['relevance_score'] = 7.5
                article['category'] = 'General'
            return articles

        analyzed = []
        
        for article in articles:
            try:
                prompt = f"""
                Analyze this news article and provide a JSON response:

                Title: {article['title']}
                Summary: {article['summary'][:200]}
                Source: {article['source']}

                Respond with ONLY a valid JSON object:
                {{
                    "relevance_score": <number 1-10>,
                    "category": "<category>",
                    "key_points": ["<point1>", "<point2>", "<point3>"],
                    "sentiment": "<positive/neutral/negative>"
                }}

                Categories: AI/ML, Technology, Business, Science, Politics, Health, Entertainment, Sports, Other
                """

                response = requests.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.gemini_api_key}',
                    headers={'Content-Type': 'application/json'},
                    json={
                        'contents': [{'parts': [{'text': prompt}]}]
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    result = response.json()
                    ai_text = result['candidates'][0]['content']['parts'][0]['text']
                    
                    # Clean and parse JSON
                    ai_text = ai_text.strip().replace('```json', '').replace('```', '')
                    ai_analysis = json.loads(ai_text)
                    
                    article.update(ai_analysis)
                else:
                    # Fallback values
                    article['relevance_score'] = 7.0
                    article['category'] = 'General'
                    article['key_points'] = []
                    article['sentiment'] = 'neutral'

            except Exception as e:
                logger.error(f"AI analysis error: {e}")
                article['relevance_score'] = 7.0
                article['category'] = 'General'
                article['key_points'] = []
                article['sentiment'] = 'neutral'
            
            analyzed.append(article)

        return analyzed

    async def latest_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /latest command"""
        # Check if we need to update cache
        if not self.articles_cache or not self.last_update or \
           (datetime.now() - self.last_update).seconds > 1800:  # 30 minutes
            await update.message.reply_text("🔄 Fetching latest news... Please wait.")
            await self.collect_news()

        if not self.articles_cache:
            await update.message.reply_text("❌ Unable to fetch news. Please try again later.")
            return

        # Sort by relevance score
        top_articles = sorted(self.articles_cache, 
                             key=lambda x: x.get('relevance_score', 0), 
                             reverse=True)[:5]

        message = f"📰 **Latest News Digest** ({len(self.articles_cache)} articles)\n"
        message += f"🕐 Last updated: {self.last_update.strftime('%H:%M %Z')}\n\n"

        for i, article in enumerate(top_articles, 1):
            score = article.get('relevance_score', 0)
            category = article.get('category', 'General')
            sentiment_emoji = {'positive': '📈', 'negative': '📉', 'neutral': '📊'}.get(
                article.get('sentiment', 'neutral'), '📊'
            )
            
            message += f"**{i}. {article['title'][:60]}...**\n"
            message += f"📂 {category} | ⭐ {score}/10 {sentiment_emoji}\n"
            message += f"🏢 {article['source']}\n"
            message += f"🔗 [Read more]({article['link']})\n\n"

        keyboard = [
            [InlineKeyboardButton("📊 Categories", callback_data='categories')],
            [InlineKeyboardButton("🔄 Refresh", callback_data='refresh')],
            [InlineKeyboardButton("📈 Trending", callback_data='trending')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            message, 
            reply_markup=reply_markup, 
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    async def show_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show news categories"""
        if not self.articles_cache:
            await update.message.reply_text("📰 No news data available. Use /latest first.")
            return

        # Count articles by category
        categories = {}
        for article in self.articles_cache:
            cat = article.get('category', 'General')
            categories[cat] = categories.get(cat, 0) + 1

        message = "📊 **News Categories**\n\n"
        
        keyboard = []
        for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            message += f"📂 **{category}**: {count} articles\n"
            keyboard.append([InlineKeyboardButton(
                f"📂 {category} ({count})", 
                callback_data=f'cat_{category}'
            )])

        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data='main_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            message, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )

    async def search_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        if not context.args:
            await update.message.reply_text("🔍 **Search News**\n\nUsage: `/search artificial intelligence`\n\nExample: `/search crypto`, `/search AI`, `/search startup`")
            return

        query = ' '.join(context.args).lower()
        
        if not self.articles_cache:
            await update.message.reply_text("📰 No news data available. Use /latest first.")
            return

        # Search in titles and summaries
        results = []
        for article in self.articles_cache:
            title_match = query in article['title'].lower()
            summary_match = query in article.get('summary', '').lower()
            
            if title_match or summary_match:
                results.append(article)

        if not results:
            await update.message.reply_text(f"🔍 No articles found for: **{query}**\n\nTry different keywords or use /latest to see all news.")
            return

        # Sort by relevance
        results = sorted(results, key=lambda x: x.get('relevance_score', 0), reverse=True)[:10]

        message = f"🔍 **Search Results for: {query}**\n"
        message += f"📊 Found {len(results)} articles\n\n"

        for i, article in enumerate(results[:5], 1):
            score = article.get('relevance_score', 0)
            category = article.get('category', 'General')
            
            message += f"**{i}. {article['title'][:60]}...**\n"
            message += f"📂 {category} | ⭐ {score}/10\n"
            message += f"🏢 {article['source']}\n"
            message += f"🔗 [Read more]({article['link']})\n\n"

        keyboard = [
            [InlineKeyboardButton("🔄 New Search", callback_data='search_help')],
            [InlineKeyboardButton("📰 Latest News", callback_data='latest')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            message, 
            reply_markup=reply_markup, 
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()

        if query.data == 'latest':
            await self.handle_latest_callback(query)
        elif query.data == 'categories':
            await self.handle_categories_callback(query)
        elif query.data == 'trending':
            await self.handle_trending_callback(query)
        elif query.data == 'refresh':
            await self.handle_refresh_callback(query)
        elif query.data.startswith('cat_'):
            await self.handle_category_callback(query)

    async def handle_latest_callback(self, query):
        """Handle latest news callback"""
        if not self.articles_cache or not self.last_update or \
           (datetime.now() - self.last_update).seconds > 1800:
            await query.edit_message_text("🔄 Fetching latest news... Please wait.")
            await self.collect_news()

        top_articles = sorted(self.articles_cache, 
                             key=lambda x: x.get('relevance_score', 0), 
                             reverse=True)[:5]

        message = f"📰 **Latest News** ({len(self.articles_cache)} articles)\n\n"

        for i, article in enumerate(top_articles, 1):
            score = article.get('relevance_score', 0)
            category = article.get('category', 'General')
            
            message += f"**{i}. {article['title'][:50]}...**\n"
            message += f"📂 {category} | ⭐ {score}/10\n"
            message += f"🔗 [Read more]({article['link']})\n\n"

        keyboard = [
            [InlineKeyboardButton("📊 Categories", callback_data='categories')],
            [InlineKeyboardButton("🔄 Refresh", callback_data='refresh')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            message, 
            reply_markup=reply_markup, 
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    async def handle_categories_callback(self, query):
        """Handle categories callback"""
        if not self.articles_cache:
            await query.edit_message_text("📰 No news data available. Use /latest first.")
            return

        categories = {}
        for article in self.articles_cache:
            cat = article.get('category', 'General')
            categories[cat] = categories.get(cat, 0) + 1

        message = "📊 **News Categories**\n\n"
        
        keyboard = []
        for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            message += f"📂 **{category}**: {count} articles\n"

        keyboard.append([InlineKeyboardButton("📰 Latest News", callback_data='latest')])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            message, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )

    async def handle_trending_callback(self, query):
        """Handle trending callback"""
        await query.edit_message_text("📈 Trending analysis coming soon!")

    async def handle_refresh_callback(self, query):
        """Handle refresh callback"""
        await query.edit_message_text("🔄 Refreshing news... Please wait.")
        await self.collect_news()
        await self.handle_latest_callback(query)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message"""
        help_text = """
🤖 **AI News Bot Commands**

📰 **/start** - Welcome & main menu
📊 **/latest** - Get latest news digest
📂 **/categories** - Browse by categories
🔍 **/search [keyword]** - Search specific topics
📈 **/trending** - Show trending stories
ℹ️ **/help** - Show this help

**Examples:**
• `/search artificial intelligence`
• `/search crypto blockchain`
• `/search startup funding`

**Features:**
✅ AI-powered article analysis
✅ Relevance scoring (1-10)
✅ Smart categorization
✅ Multi-source aggregation
✅ Real-time updates

**Powered by Gemini AI** 🚀
        """
        
        keyboard = [
            [InlineKeyboardButton("📰 Get Started", callback_data='latest')],
            [InlineKeyboardButton("📊 Categories", callback_data='categories')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            help_text, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )

    def run(self):
        """Start the bot"""
        if not self.bot_token:
            logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
            return

        application = Application.builder().token(self.bot_token).build()

        # Add handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("latest", self.latest_news))
        application.add_handler(CommandHandler("categories", self.show_categories))
        application.add_handler(CommandHandler("search", self.search_news))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CallbackQueryHandler(self.button_handler))

        logger.info("🚀 AI News Bot started!")
        application.run_polling()

if __name__ == '__main__':
    bot = AINewsTelegramBot()
    bot.run()
