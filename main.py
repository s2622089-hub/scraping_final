import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import re

# GoogleのGitHubリポジトリ一覧
BASE_URL = "https://github.com/orgs/google/repositories"

# データベース接続
conn = sqlite3.connect("repositories.db")
cursor = conn.cursor()

# テーブル作成
cursor.execute("""
CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    language TEXT,
    stars INTEGER
)
""")

conn.commit()

# HTTPリクエスト設定
headers = {
    "User-Agent": "Mozilla/5.0"
}

page = 1
total_count = 0
seen_repos = set()

while True:
    print(f"\n{page}ページ目を取得中...")

    url = f"{BASE_URL}?page={page}&per_page=30"

    # 最大3回まで再取得する
    response = None

    for attempt in range(3):
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=30
            )

            print("HTTPステータス:", response.status_code)

            if response.status_code == 200:
                break

            print("取得に失敗しました。10秒待ちます。")
            time.sleep(10)

        except requests.RequestException as e:
            print("通信エラー:", e)
            time.sleep(10)

    # 3回失敗した場合は終了
    if response is None or response.status_code != 200:
        print("3回失敗したため終了します。")
        break

    soup = BeautifulSoup(response.text, "html.parser")

    # リポジトリ一覧を取得
    repo_links = soup.select(
        'h3 a[href^="/google/"]'
    )

    print("取得したリポジトリ数:", len(repo_links))

    # リポジトリが見つからない場合
    if not repo_links:
        print(f"{page}ページ目でリポジトリが見つかりません。")

        # HTMLを保存して確認できるようにする
        with open(
            f"debug_page_{page}.html",
            "w",
            encoding="utf-8"
        ) as f:
            f.write(response.text)

        print("HTMLを保存しました。")

        if soup.title:
            print(
                "ページタイトル:",
                soup.title.get_text(strip=True)
            )

        break

    # 各リポジトリの情報を取得
    for repo_link in repo_links:

        # リポジトリ名とURL
        repo_name = repo_link.get_text(strip=True)
        repo_path = repo_link.get("href", "").rstrip("/")

        if not repo_path or repo_path in seen_repos:
            continue

        seen_repos.add(repo_path)

        # スターのリンク
        star_href = repo_path + "/stargazers"

        # リポジトリの親要素を探す
        repo_box = None

        for parent in repo_link.parents:
            if parent.select_one(
                f'a[href="{star_href}"]'
            ):
                repo_box = parent
                break

        if repo_box is None:
            print(repo_name, "の情報が見つかりません")
            continue

        # 主要なプログラミング言語を取得
        language_tag = repo_box.select_one(
            '[itemprop="programmingLanguage"]'
        )

        if language_tag:
            language = language_tag.get_text(strip=True)
        else:
            language = "Unknown"

        # スター数を取得
        star_tag = repo_box.select_one(
            f'a[href="{star_href}"]'
        )

        stars = 0

        if star_tag:
            star_text = star_tag.get_text(" ", strip=True)
            star_text = star_text.replace(",", "")

            # 1.2kなどの表記にも対応
            match = re.search(
                r"([\d.]+)\s*([kKmM]?)",
                star_text
            )

            if match:
                number = float(match.group(1))
                unit = match.group(2).lower()

                if unit == "k":
                    number *= 1000
                elif unit == "m":
                    number *= 1000000

                stars = int(number)

        # データベースに保存
        cursor.execute("""
            INSERT OR REPLACE INTO repositories
            (name, language, stars)
            VALUES (?, ?, ?)
        """, (repo_name, language, stars))

        total_count += 1

        print(
            "取得:",
            repo_name,
            language,
            stars
        )

    # データを保存
    conn.commit()

    # 次のページへ
    page += 1

    # サーバーへの負荷を減らすため1秒待つ
    time.sleep(1)

print("\nスクレイピング終了")
print("今回の取得件数:", total_count)

# SELECT文で全件表示
print("\n===== データベースの内容 =====")

cursor.execute("""
SELECT name, language, stars
FROM repositories
ORDER BY stars DESC
""")

rows = cursor.fetchall()

for row in rows:
    print(
        "リポジトリ名:", row[0],
        "| 言語:", row[1],
        "| スター数:", row[2]
    )

print("\nデータベースの保存件数:", len(rows))

conn.close()
