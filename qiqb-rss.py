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
        
        for target_url in [list_url, base_url]:
            print(f"URLを収集します: {target_url}")
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
            exclude_keywords = ['list', 'category', 'page', 'tag']
            
            for url in set(article_urls):
                url = url.split('#')[0].split('?')[0]
                if not any(x in url for x in exclude_keywords):
                    if url.rstrip('/') != "https://qiqb.osaka-u.ac.jp/newstopics":
                        clean_urls.append(url)
            
            article_urls = clean_urls
            if article_urls:
                break
            time.sleep(1)

        print(f"発見した記事リンク数: {len(article_urls)}件")

        if not article_urls:
            print("❌ 記事のリンクが見つかりません。")
            sys.exit(1)

        # 💡 成功した記事だけをカウントするための変数
        added_count = 0

        # 全てのURLを順番に試す（最大10件成功するまで）
        for url in article_urls:
            if added_count >= 10:
                break # 10件集まったら終了

            print(f"記事を取得中: {url}")
            time.sleep(1)
            
            # 💡 修正ポイント：個別の記事取得でエラーが出ても、止まらずにスキップする
            try:
                detail_res = session.get(url, timeout=20)
                detail_res.raise_for_status() # 404などのエラー判定
            except requests.exceptions.RequestException as e:
                print(f"  -> ⚠️ スキップします（404エラーなど削除された記事の可能性）: {e}")
                continue # エラーが起きたら、下の処理をやらずに次のURLへ行く！

            detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
            
            title_tag = detail_soup.find('h1')
            if title_tag and title_tag.get_text(strip=True):
                article_title = title_tag.get_text(strip=True)
            elif detail_soup.title:
                article_title = detail_soup.title.get_text(strip=True).split('|')[0].strip()
            else:
                article_title = "タイトルなし"
                
            print(f"  -> 解析成功: {article_title}")
            
            article_box = detail_soup.find(['article', 'main']) or detail_soup.find('div', class_=re.compile(r'content|post|detail|entry|news_detail', re.I))
            
            if article_box and len(article_box.get_text(strip=True)) > 50:
                for img in article_box.find_all('img'):
                    src = img.get('src')
                    if src:
                        img['src'] = urljoin(url, src)
                content_html = str(article_box)
            else:
                meta_desc = detail_soup.find('meta', attrs={'name': 'description'}) or detail_soup.find('meta', property='og:description')
                if meta_desc and meta_desc.get('content'):
                    content_html = f"<p>【要約】<br>{meta_desc.get('content')}</p><p><a href='{url}'>記事の全文はこちら</a></p>"
                else:
                    content_html = f"<p>本文の抽出に失敗しました。<a href='{url}'>記事の全文はこちら</a></p>"
            
            fe = fg.add_entry()
            fe.id(url)
            fe.title(article_title)
            fe.link(href=url)
            fe.description(content_html)
            fe.pubDate(datetime.datetime.now(datetime.timezone.utc))
            
            added_count += 1 # 成功した数を1増やす

        output_file = 'feed.xml'
        fg.rss_file(output_file)
        print(f"✅ 成功: {output_file} を書き出しました！（合計 {added_count} 件）")

    except Exception as e:
        print(f"💥 全体エラー内容: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_rss()
