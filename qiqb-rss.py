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

    print("--- QIQBニュース 解析開始 ---")

    try:
        article_urls = []
        
        # 💡 SPA対策：一覧ページがダメならトップページも探す「2段構え」
        for target_url in [list_url, base_url]:
            print(f"URLを収集します: {target_url}")
            res = session.get(target_url, timeout=20)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 方法1：通常の <a> タグ探索
            for a in soup.find_all('a', href=True):
                full_url = urljoin(res.url, a['href'])
                if '/newstopics/' in full_url:
                    article_urls.append(full_url)
            
            # 💡 方法2（最強）：裏側に隠されたJSONや文字列から、URLの痕跡を直接スキャンする
            for match in re.findall(r'/newstopics/([a-zA-Z0-9_-]+)', res.text):
                article_urls.append(f"https://qiqb.osaka-u.ac.jp/newstopics/{match}")

            # 集めたURLのゴミ取り（重複や不要なページを消す）
            clean_urls = []
            exclude_keywords = ['list', 'category', 'page', 'tag']
            
            for url in set(article_urls):
                url = url.split('#')[0].split('?')[0] # ハッシュ等を削除
                if not any(x in url for x in exclude_keywords):
                    if url.rstrip('/') != "https://qiqb.osaka-u.ac.jp/newstopics":
                        clean_urls.append(url)
            
            article_urls = clean_urls
            
            if article_urls:
                break # 1件でも見つかったら探索終了！
            
            time.sleep(1)

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
            
            # 1. タイトルを探す（SPA対策で <title> も重視）
            title_tag = detail_soup.find('h1')
            if title_tag and title_tag.get_text(strip=True):
                article_title = title_tag.get_text(strip=True)
            elif detail_soup.title:
                # 「 | QIQB：...」の部分を削って綺麗なタイトルに
                article_title = detail_soup.title.get_text(strip=True).split('|')[0].strip()
            else:
                article_title = "タイトルなし"
                
            print(f"  -> 解析成功: {article_title}")
            
            # 2. 本文を探す
            article_box = detail_soup.find(['article', 'main']) or detail_soup.find('div', class_=re.compile(r'content|post|detail|entry|news_detail', re.I))
            
            if article_box and len(article_box.get_text(strip=True)) > 50:
                for img in article_box.find_all('img'):
                    src = img.get('src')
                    if src:
                        img['src'] = urljoin(url, src)
                content_html = str(article_box)
            else:
                # 💡 本文すらJavaScriptで隠されていた場合の最強バックアップ
                # Google検索結果などに表示される「メタディスクリプション（要約）」を抜き出す
                meta_desc = detail_soup.find('meta', attrs={'name': 'description'}) or detail_soup.find('meta', property='og:description')
                if meta_desc and meta_desc.get('content'):
                    content_html = f"<p>【要約】<br>{meta_desc.get('content')}</p><p><a href='{url}'>記事の全文はこちら（ブラウザで開きます）</a></p>"
                else:
                    content_html = f"<p>本文の抽出に失敗しました。<a href='{url}'>記事の全文はこちら</a></p>"
            
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
