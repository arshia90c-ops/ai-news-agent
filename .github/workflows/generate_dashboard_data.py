#!/usr/bin/env python3
"""
Dashboard Data Generator for AI News Agent
Creates a static HTML dashboard from collected data
"""

import os
import json
import glob
from datetime import datetime, timedelta
from collections import defaultdict, Counter

class DashboardGenerator:
    def __init__(self):
        self.data_dir = 'data'
        self.dashboard_dir = 'dashboard'
        
    def load_all_data(self):
        """Load all collected data files"""
        all_data = []
        
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Find all JSON files in data directory
        json_files = glob.glob(os.path.join(self.data_dir, '*.json'))
        
        for file_path in sorted(json_files):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    all_data.append(data)
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                continue
        
        return all_data
    
    def generate_statistics(self, all_data):
        """Generate statistics from collected data"""
        if not all_data:
            return {
                'total_articles': 0,
                'total_sources': 0,
                'days_tracked': 0,
                'top_sources': [],
                'category_distribution': {},
                'daily_counts': {}
            }
        
        # Aggregate statistics
        all_articles = []
        daily_counts = defaultdict(int)
        source_counts = Counter()
        category_counts = Counter()
        
        for day_data in all_data:
            articles = day_data.get('articles', [])
            all_articles.extend(articles)
            
            # Daily article count
            date_key = day_data.get('timestamp', '')[:10]  # YYYY-MM-DD
            daily_counts[date_key] = len(articles)
            
            # Source counts
            for article in articles:
                source_counts[article.get('source', 'Unknown')] += 1
            
            # Category counts
            categories = day_data.get('analysis', {}).get('categories', {})
            for category, titles in categories.items():
                category_counts[category] += len(titles)
        
        return {
            'total_articles': len(all_articles),
            'total_sources': len(source_counts),
            'days_tracked': len(all_data),
            'top_sources': source_counts.most_common(10),
            'category_distribution': dict(category_counts),
            'daily_counts': dict(daily_counts)
        }
    
    def generate_html_dashboard(self, all_data, stats):
        """Generate complete HTML dashboard"""
        now = datetime.now()
        
        # Recent articles (last 50)
        recent_articles = []
        for day_data in sorted(all_data, key=lambda x: x.get('timestamp', ''), reverse=True):
            articles = day_data.get('articles', [])
            recent_articles.extend(articles)
            if len(recent_articles) >= 50:
                break
        
        recent_articles = recent_articles[:50]
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>AI News Intelligence Dashboard</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8fafc; color: #334155; }}
                .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; border-radius: 12px; text-align: center; margin-bottom: 30px; }}
                .header h1 {{ font-size: 36px; font-weight: 300; margin-bottom: 10px; }}
                .header p {{ opacity: 0.9; font-size: 18px; }}
                .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                .stat-card {{ background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }}
                .stat-number {{ font-size: 32px; font-weight: bold; color: #667eea; margin-bottom: 5px; }}
                .stat-label {{ color: #64748b; font-size: 14px; }}
                .section {{ background: white; padding: 30px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .section h2 {{ color: #1e293b; margin-bottom: 20px; font-size: 24px; }}
                .articles-grid {{ display: grid; gap: 20px; }}
                .article-card {{ border: 1px solid #e2e8f0; border-radius: 6px; padding: 20px; transition: all 0.2s; }}
                .article-card:hover {{ border-color: #667eea; transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
                .article-title {{ font-size: 18px; font-weight: 600; margin-bottom: 10px; }}
                .article-title a {{ color: #1e293b; text-decoration: none; }}
                .article-title a:hover {{ color: #667eea; }}
                .article-description {{ color: #64748b; margin-bottom: 15px; line-height: 1.5; }}
                .article-meta {{ display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #94a3b8; }}
                .source-tag {{ background: #f1f5f9; padding: 4px 8px; border-radius: 4px; color: #475569; }}
                .search-box {{ width: 100%; padding: 12px; border: 1px solid #d1d5db; border-radius: 6px; margin-bottom: 20px; font-size: 16px; }}
                .filter-buttons {{ display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }}
                .filter-btn {{ padding: 8px 16px; border: 1px solid #d1d5db; background: white; border-radius: 6px; cursor: pointer; transition: all 0.2s; }}
                .filter-btn:hover {{ background: #667eea; color: white; border-color: #667eea; }}
                .filter-btn.active {{ background: #667eea; color: white; border-color: #667eea; }}
                .top-sources {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
                .source-item {{ display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #f8fafc; border-radius: 6px; }}
                .last-updated {{ text-align: center; color: #64748b; margin-top: 30px; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔍 AI News Intelligence Dashboard</h1>
                    <p>Real-time analysis of technology and AI news trends</p>
                    <p>Last updated: {now.strftime('%A, %B %d, %Y at %I:%M %p UTC')}</p>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number">{stats['total_articles']}</div>
                        <div class="stat-label">Total Articles Analyzed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['total_sources']}</div>
                        <div class="stat-label">News Sources Monitored</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['days_tracked']}</div>
                        <div class="stat-label">Days of Data Collection</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{len(recent_articles)}</div>
                        <div class="stat-label">Recent Articles</div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>📊 Top News Sources</h2>
                    <div class="top-sources">
        """
        
        # Add top sources
        for source, count in stats['top_sources'][:8]:
            html_content += f"""
                        <div class="source-item">
                            <span>{source}</span>
                            <span><strong>{count}</strong> articles</span>
                        </div>
            """
        
        html_content += """
                    </div>
                </div>
                
                <div class="section">
                    <h2>📰 Recent Articles</h2>
                    <input type="text" class="search-box" id="searchBox" placeholder="🔍 Search articles..." onkeyup="filterArticles()">
                    
                    <div class="filter-buttons">
                        <button class="filter-btn active" onclick="filterByCategory('all')">All</button>
        """
        
        # Add category filter buttons
        categories = set()
        for day_data in all_data:
            categories.update(day_data.get('analysis', {}).get('categories', {}).keys())
        
        for category in sorted(categories):
            html_content += f'<button class="filter-btn" onclick="filterByCategory(\'{category}\')">{category}</button>'
        
        html_content += """
                    </div>
                    
                    <div class="articles-grid" id="articlesContainer">
        """
        
        # Add recent articles
        for i, article in enumerate(recent_articles):
            # Determine category for filtering
            article_categories = []
            for day_data in all_data:
                categories = day_data.get('analysis', {}).get('categories', {})
                for category, titles in categories.items():
                    if article['title'] in titles:
                        article_categories.append(category)
            
            category_classes = ' '.join(article_categories) if article_categories else 'Other'
            
            html_content += f"""
                        <div class="article-card" data-category="{category_classes}">
                            <div class="article-title">
                                <a href="{article['url']}" target="_blank">{article['title']}</a>
                            </div>
                            <div class="article-description">{article['description'][:150]}...</div>
                            <div class="article-meta">
                                <span class="source-tag">{article['source']}</span>
                                <span>{datetime.fromisoformat(article['published']).strftime('%b %d, %Y')}</span>
                            </div>
                        </div>
            """
        
        html_content += f"""
                    </div>
                </div>
                
                <div class="last-updated">
                    <p>🤖 Generated by AI News Intelligence Agent</p>
                    <p>Dashboard automatically updates with each news collection cycle</p>
                </div>
            </div>
            
            <script>
                function filterArticles() {{
                    const searchTerm = document.getElementById('searchBox').value.toLowerCase();
                    const articles = document.querySelectorAll('.article-card');
                    
                    articles.forEach(article => {{
                        const title = article.querySelector('.article-title').textContent.toLowerCase();
                        const description = article.querySelector('.article-description').textContent.toLowerCase();
                        
                        if (title.includes(searchTerm) || description.includes(searchTerm)) {{
                            article.style.display = 'block';
                        }} else {{
                            article.style.display = 'none';
                        }}
                    }});
                }}
                
                function filterByCategory(category) {{
                    const articles = document.querySelectorAll('.article-card');
                    const buttons = document.querySelectorAll('.filter-btn');
                    
                    // Update button states
                    buttons.forEach(btn => btn.classList.remove('active'));
                    event.target.classList.add('active');
                    
                    // Filter articles
                    articles.forEach(article => {{
                        if (category === 'all' || article.dataset.category.includes(category)) {{
                            article.style.display = 'block';
                        }} else {{
                            article.style.display = 'none';
                        }}
                    }});
                }}
            </script>
        </body>
        </html>
        """
        
        return html_content
    
    def generate(self):
        """Generate dashboard files"""
        print("🎨 Generating dashboard...")
        
        # Create dashboard directory
        os.makedirs(self.dashboard_dir, exist_ok=True)
        
        # Load all data
        all_data = self.load_all_data()
        
        if not all_data:
            print("⚠️  No data found, creating placeholder dashboard...")
            # Create a basic placeholder
            placeholder_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>AI News Dashboard</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .placeholder { color: #666; }
                </style>
            </head>
            <body>
                <h1>🔍 AI News Intelligence Dashboard</h1>
                <div class="placeholder">
                    <p>Dashboard is being prepared...</p>
                    <p>Check back after the first news collection runs!</p>
                </div>
            </body>
            </html>
            """
            
            with open(os.path.join(self.dashboard_dir, 'index.html'), 'w') as f:
                f.write(placeholder_html)
            
            return
        
        # Generate statistics
        stats = self.generate_statistics(all_data)
        
        # Generate HTML dashboard
        html_content = self.generate_html_dashboard(all_data, stats)
        
        # Save dashboard
        with open(os.path.join(self.dashboard_dir, 'index.html'), 'w') as f:
            f.write(html_content)
        
        # Save raw data as JSON for potential API access
        dashboard_data = {
            'generated_at': datetime.now().isoformat(),
            'statistics': stats,
            'recent_data': all_data[-7:] if len(all_data) > 7 else all_data  # Last 7 days
        }
        
        with open(os.path.join(self.dashboard_dir, 'data.json'), 'w') as f:
            json.dump(dashboard_data, f, indent=2)
        
        print(f"✅ Dashboard generated with {stats['total_articles']} articles from {stats['days_tracked']} days")
        print(f"📊 Dashboard available at: dashboard/index.html")

def main():
    generator = DashboardGenerator()
    generator.generate()

if __name__ == "__main__":
    main()
