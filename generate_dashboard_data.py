import json
import os
from datetime import datetime, timedelta
import glob

def generate_dashboard_data():
    """Generate dashboard data from collected articles"""
    print("📊 Generating dashboard data...")
    
    try:
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        
        # If no articles data exists yet, create empty structure
        if not os.path.exists('data/latest.json'):
            print("⚠️ No articles data found, creating empty dashboard data...")
            
            empty_data = {
                'date': datetime.now().isoformat(),
                'articles': [],
                'summary': {
                    'total_articles': 0,
                    'avg_relevance': 0,
                    'categories': [],
                    'sources': []
                },
                'trends': {
                    'daily_counts': [],
                    'category_distribution': {},
                    'source_distribution': {},
                    'relevance_trend': []
                }
            }
            
            # Save empty data
            with open('data/latest.json', 'w') as f:
                json.dump(empty_data, f, indent=2)
            
            with open('data/dashboard_data.json', 'w') as f:
                json.dump(empty_data, f, indent=2)
            
            print("✅ Empty dashboard data created")
            return
        
        # Load latest articles data
        with open('data/latest.json', 'r') as f:
            latest_data = json.load(f)
        
        # Collect historical data from all daily files
        historical_data = []
        data_files = glob.glob('data/articles_*.json')
        
        for file_path in data_files:
            try:
                with open(file_path, 'r') as f:
                    daily_data = json.load(f)
                    historical_data.append(daily_data)
            except Exception as e:
                print(f"⚠️ Error reading {file_path}: {str(e)}")
                continue
        
        # Sort by date
        historical_data.sort(key=lambda x: x.get('date', ''))
        
        # Generate trends
        trends = generate_trends(historical_data)
        
        # Create comprehensive dashboard data
        dashboard_data = {
            'last_updated': datetime.now().isoformat(),
            'latest_articles': latest_data.get('articles', [])[:20],  # Top 20 articles
            'summary': latest_data.get('summary', {}),
            'trends': trends,
            'historical_summary': {
                'total_days': len(historical_data),
                'total_articles_collected': sum(d.get('summary', {}).get('total_articles', 0) for d in historical_data),
                'date_range': {
                    'start': historical_data[0].get('date') if historical_data else None,
                    'end': historical_data[-1].get('date') if historical_data else None
                }
            }
        }
        
        # Save dashboard data
        with open('data/dashboard_data.json', 'w') as f:
            json.dump(dashboard_data, f, indent=2)
        
        # Generate HTML dashboard
        generate_html_dashboard(dashboard_data)
        
        print(f"✅ Dashboard data generated with {len(dashboard_data['latest_articles'])} articles")
        
    except Exception as e:
        print(f"❌ Error generating dashboard data: {str(e)}")
        raise

def generate_trends(historical_data):
    """Generate trend analysis from historical data"""
    if not historical_data:
        return {
            'daily_counts': [],
            'category_distribution': {},
            'source_distribution': {},
            'relevance_trend': []
        }
    
    trends = {
        'daily_counts': [],
        'category_distribution': {},
        'source_distribution': {},
        'relevance_trend': []
    }
    
    # Daily article counts
    for day_data in historical_data:
        date = day_data.get('date', '')[:10]  # Get just the date part
        article_count = day_data.get('summary', {}).get('total_articles', 0)
        avg_relevance = day_data.get('summary', {}).get('avg_relevance', 0)
        
        trends['daily_counts'].append({
            'date': date,
            'count': article_count
        })
        
        trends['relevance_trend'].append({
            'date': date,
            'avg_relevance': round(avg_relevance, 1)
        })
    
    # Category distribution (from all historical data)
    all_articles = []
    for day_data in historical_data:
        all_articles.extend(day_data.get('articles', []))
    
    # Count categories
    category_counts = {}
    source_counts = {}
    
    for article in all_articles:
        # Categories
        category = article.get('category', 'Other')
        category_counts[category] = category_counts.get(category, 0) + 1
        
        # Sources
        source = article.get('source', 'Unknown')
        source_counts[source] = source_counts.get(source, 0) + 1
    
    trends['category_distribution'] = category_counts
    trends['source_distribution'] = dict(list(source_counts.items())[:15])  # Top 15 sources
    
    return trends

def generate_html_dashboard(data):
    """Generate HTML dashboard file"""
    try:
        articles = data.get('latest_articles', [])
        summary = data.get('summary', {})
        trends = data.get('trends', {})
        
        # Generate category cards
        categories = {}
        for article in articles:
            cat = article.get('category', 'Other')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(article)
        
        category_cards = ""
        for category, cat_articles in categories.items():
            avg_score = sum(a.get('relevance_score', 0) for a in cat_articles) / len(cat_articles) if cat_articles else 0
            
            articles_html = ""
            for article in cat_articles[:5]:  # Top 5 per category
                articles_html += f"""
                    <div class="article-item">
                        <div class="article-title">
                            <a href="{article.get('url', '#')}" target="_blank">{article.get('title', 'No title')}</a>
                            <span class="score">{article.get('relevance_score', 'N/A')}</span>
                        </div>
                        <div class="article-meta">{article.get('source', 'Unknown')} • {article.get('importance_level', 'medium').title()}</div>
                    </div>
                """
            
            category_cards += f"""
                <div class="category-card">
                    <div class="category-header">
                        <h3>{category}</h3>
                        <div class="category-stats">
                            <span class="article-count">{len(cat_articles)} articles</span>
                            <span class="avg-score">Avg: {avg_score:.1f}</span>
                        </div>
                    </div>
                    <div class="articles-list">
                        {articles_html}
                    </div>
                </div>
            """
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI News Intelligence Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .dashboard {{ 
            max-width: 1200px; 
            margin: 0 auto; 
            background: white; 
            border-radius: 15px; 
            overflow: hidden; 
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}
        .header {{ 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            padding: 30px; 
            text-align: center; 
        }}
        .header h1 {{ font-size: 32px; margin-bottom: 10px; }}
        .header p {{ opacity: 0.9; font-size: 16px; }}
        .stats-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 20px; 
            padding: 30px; 
            background: #f8f9fa; 
        }}
        .stat-card {{ 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            text-align: center; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }}
        .stat-number {{ 
            font-size: 28px; 
            font-weight: bold; 
            color: #667eea; 
            margin-bottom: 5px; 
        }}
        .stat-label {{ color: #666; font-size: 14px; }}
        .content {{ padding: 30px; }}
        .section {{ margin-bottom: 40px; }}
        .section h2 {{ 
            color: #333; 
            margin-bottom: 20px; 
            font-size: 24px; 
            border-bottom: 2px solid #667eea; 
            padding-bottom: 10px; 
        }}
        .categories-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 20px; 
        }}
        .category-card {{ 
            background: #f8f9fa; 
            border-radius: 10px; 
            overflow: hidden; 
            border: 1px solid #eee; 
        }}
        .category-header {{ 
            background: #667eea; 
            color: white; 
            padding: 15px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
        }}
        .category-header h3 {{ font-size: 18px; }}
        .category-stats {{ 
            font-size: 12px; 
            opacity: 0.9; 
        }}
        .category-stats span {{ 
            margin-left: 10px; 
            background: rgba(255,255,255,0.2); 
            padding: 4px 8px; 
            border-radius: 12px; 
        }}
        .articles-list {{ padding: 15px; }}
        .article-item {{ 
            padding: 10px 0; 
            border-bottom: 1px solid #eee; 
        }}
        .article-item:last-child {{ border-bottom: none; }}
        .article-title {{ 
            display: flex; 
            justify-content: space-between; 
            align-items: flex-start; 
            margin-bottom: 5px; 
        }}
        .article-title a {{ 
            color: #333; 
            text-decoration: none; 
            font-weight: 500; 
            flex-grow: 1; 
            margin-right: 10px; 
            line-height: 1.4; 
        }}
        .article-title a:hover {{ color: #667eea; }}
        .score {{ 
            background: #667eea; 
            color: white; 
            padding: 2px 8px; 
            border-radius: 12px; 
            font-size: 11px; 
            white-space: nowrap; 
        }}
        .article-meta {{ 
            color: #666; 
            font-size: 12px; 
        }}
        .footer {{ 
            text-align: center; 
            padding: 20px; 
            background: #f8f9fa; 
            border-top: 1px solid #eee; 
            color: #666; 
        }}
        .empty-state {{ 
            text-align: center; 
            padding: 60px 20px; 
            color: #666; 
        }}
        .empty-state h3 {{ color: #333; margin-bottom: 10px; }}
        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); padding: 20px; }}
            .categories-grid {{ grid-template-columns: 1fr; }}
            .content {{ padding: 20px; }}
            body {{ padding: 10px; }}
        }}
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>🤖 AI News Intelligence</h1>
            <p>Live Dashboard • Last updated: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{len(articles)}</div>
                <div class="stat-label">Articles Today</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(categories)}</div>
                <div class="stat-label">Categories</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(set(a.get('source', '') for a in articles))}</div>
                <div class="stat-label">Sources</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{int(sum(a.get('relevance_score', 0) for a in articles) / len(articles)) if articles else 0}</div>
                <div class="stat-label">Avg Relevance</div>
            </div>
        </div>
        
        <div class="content">
            {f'''
            <div class="section">
                <h2>📊 Latest Articles by Category</h2>
                <div class="categories-grid">
                    {category_cards}
                </div>
            </div>
            ''' if articles else '''
            <div class="empty-state">
                <h3>🚀 Dashboard Ready</h3>
                <p>Your AI News Agent is set up! Articles will appear here after the first successful run.</p>
                <p>Check back in a few minutes, or trigger a manual run from the Actions tab.</p>
            </div>
            '''}
        </div>
        
        <div class="footer">
            <p>🤖 Powered by AI News Intelligence Agent • Built with GitHub Actions & Gemini AI</p>
        </div>
    </div>
</body>
</html>
        """
        
        # Save HTML dashboard
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print("✅ HTML dashboard generated")
        
    except Exception as e:
        print(f"❌ Error generating HTML dashboard: {str(e)}")
        raise

if __name__ == "__main__":
    generate_dashboard_data()
