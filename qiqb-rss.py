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
    # QIQBのニュース一覧ページ
    list_url = "https://qiqb.osaka-u.ac.jp/newstopics/list"
    
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

    print("--- QIQBニュース 解析開始 ---")

    try:
        print(f"一覧ページからURLを収集します: {list_url}")
        res = session.get(list_url, timeout=20)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        article_urls = []
        for a in soup.find_all('a', href=True):
            # 💡 修正ポイント：先にURLを「完全な形」に翻訳してから判定する！
            full_url = urljoin(res.url, a['href'])
            
            # /newstopics/ が含まれていて、かつ一覧ページやカテゴリ一覧ではない記事URLを拾う
            if '/newstopics/' in full_url and not any(x in full_url for x in ['list', 'category', 'page']):
                # URLの末尾が /newstopics/ や /newstopics 自体でないことも確認
                if full_url.rstrip('/') != "https://qiqb.osaka-u.ac.jp/newstopics":
                    if full_url not in article_urls:
                        article_urls.append(full_url)

        print(f"発見した記事リンク数: {len(article_urls)}件")

        if not article_urls:
            print("❌ 記事のリンクが見つかりません。")
            sys.exit(1)

        # 最新10件を取得
        for url in article_urls[:10]:
            print(f"記事を取得中: {url}")
            time.sleep(1)
            
            detail_res = session.get(url, timeout=20)
            detail_res.raise_for_status()
            detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
            
            # 1. タイトルを探す
            title_tag = detail_soup.find('h1')
            if title_tag:
                article_title = title_tag.get_text(strip=True)
            elif detail_soup.title:
                article_title = detail_soup.title.get_text(strip=True).split('|')[0].strip()
            else:
                article_title = "タイトルなし"
                
            print(f"  -> 解析成功: {article_title}")
            
            # 2. 本文を探す（大学や研究機関のサイトでよく使われるクラス名を網羅）
            article_box = detail_soup.find(['article', 'main']) or detail_soup.find('div', class_=re.compile(r'content|post|detail|entry|news_detail', re.I))
            
            content_html = "<p>本文の抽出に失敗しました。</p>"
            if article_box:
                for img in article_box.find_all('img'):
                    src = img.get('src')
                    if src:
                        img['src'] = urljoin(url, src)
                content_html = str(article_box)
            
            fe = fg.add_entry()
            fe.id(url)
            fe.title(article_title)
            fe.link(href=url)
            fe.description(content_html)
            fe.pubDate(datetime.datetime.now(datetime.timezone.utc))

        output_file = 'feed.xml'
        fg.rss_file(output_file)
        print(f"✅ 成功: {output_file} を書き出しました！")

    except Exception as e:
        print(f"💥 エラー内容: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_rss()
