import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import datetime
import time
import os
import sys
import re
from urllib.parse import urljoin

def create_rss():
    list_url = "https://qiqb.osaka-u.ac.jp/newstopics/list"
    base_url = "https://qiqb.osaka-u.ac.jp/"
    
    fg = FeedGenerator()
    fg.id(list_url)
    fg.title("大阪大学 QIQB 最新ニュース RSS")
    fg.link(href=list_url, rel='alternate')
    fg.description("大阪大学 量子情報・量子生命研究センター(QIQB)のニュースとプレスリリース")
    fg.language('ja')

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    })

    print("--- QIQBニュース 解析開始 (ハイブリッド要約抽出版V5) ---")

    try:
        article_urls = []
        for target_url in [list_url, base_url]:
            res = session.get(target_url, timeout=20)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            
            for a in soup.find_all('a', href=True):
                full_url = urljoin(res.url, a['href'])
                if '/newstopics/' in full_url:
                    article_urls.append(full_url)
            
            for match in re.findall(r'/newstopics/([a-zA-Z0-9_-]+)', res.text):
                article_urls.append(f"https://qiqb.osaka-u.ac.jp/newstopics/{match}")

            clean_urls = []
            for url in set(article_urls):
                url = url.split('#')[0].split('?')[0]
                if not any(x in url for x in ['list', 'category', 'page', 'tag']):
                    if url.rstrip('/') != "https://qiqb.osaka-u.ac.jp/newstopics":
                        clean_urls.append(url)
            
            article_urls = clean_urls
            if article_urls:
                break
            time.sleep(1)

        print(f"発見した記事リンク数: {len(article_urls)}件")
        if not article_urls:
            sys.exit(1)

        added_count = 0
        for url in article_urls:
            if added_count >= 10: break 
            print(f"記事を取得中: {url}")
            time.sleep(1)
            
            try:
                detail_res = session.get(url, timeout=20)
                detail_res.raise_for_status()
                detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
                
                title_tag = detail_soup.find('h1')
                if title_tag and title_tag.get_text(strip=True):
                    article_title = title_tag.get_text(strip=True)
                elif detail_soup.title:
                    article_title = detail_soup.title.get_text(strip=True).split('|')[0].strip()
                else:
                    article_title = "タイトルなし"
                    
                article_box = None
                for class_name in ['content', 'post', 'detail', 'entry', 'news-detail', 'article-body', 'entry-content']:
                    box = detail_soup.find('div', class_=re.compile(class_name, re.I))
                    if box and len(box.get_text(strip=True)) > 50:
                        article_box = box
                        break
                
                if not article_box:
                    article_box = detail_soup.find('article') or detail_soup.find('main')

                if article_box and len(article_box.get_text(strip=True)) > 50:
                    for img in article_box.find_all('img'):
                        if img.get('src'):
                            img['src'] = urljoin(url, img['src'])
                    content_html = str(article_box)
                else:
                    html_parts = []
                    for p in detail_soup.find_all('p'):
                        if len(p.get_text(strip=True)) > 20:
                            for img in p.find_all('img'):
                                if img.get('src'):
                                    img['src'] = urljoin(url, img['src'])
                            html_parts.append(str(p))
                    
                    if html_parts:
                        content_html = f"<div>{''.join(html_parts)}</div>"
                    else:
                        # 💡 究極のバックアップ：検索エンジン用の「要約」を抜き出す！
                        meta_desc = detail_soup.find('meta', attrs={'name': 'description'}) or detail_soup.find('meta', property='og:description')
                        if meta_desc and meta_desc.get('content'):
                            content_html = f"<p><strong>【記事の要約】</strong><br>{meta_desc.get('content')}</p><p><br><em>※この記事は特殊な構造のため、全文は公式サイトでご覧ください。</em><br><a href='{url}'>👉 記事の全文を読む</a></p>"
                        else:
                            content_html = f"<p>本文の抽出に失敗しました。<a href='{url}'>記事の全文はこちら</a></p>"
                
                fe = fg.add_entry()
                fe.id(url)
                fe.title(article_title)
                fe.link(href=url)
                fe.description(content_html)
                fe.pubDate(datetime.datetime.now(datetime.timezone.utc))
                
                added_count += 1 
                print("  -> 追加成功")

            except Exception as e:
                print(f"  -> ⚠️ スキップ ({e})")
                continue

        output_file = 'feed.xml'
        fg.rss_file(output_file)
        print(f"✅ 成功: {output_file} を書き出しました！（合計 {added_count} 件）")

    except Exception as e:
        print(f"💥 システムエラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_rss()
