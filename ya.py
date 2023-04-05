import webbrowser
import os
import sqlite3
import google_auth_oauthlib.flow
from google.oauth2.credentials import Credentials
import googleapiclient.discovery
import googleapiclient.errors
import json


def authenticate():
    scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
    api_version = "v3"
    client_secrets_file = "client_secrets.json"
    credentials_file = "credentials.json"

    credentials = None

    if os.path.exists(credentials_file):
        with open(credentials_file, "r") as file:
            credentials_json = json.load(file)
            credentials = Credentials.from_authorized_user_info(
                info=credentials_json, scopes=scopes)
    else:
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, scopes)
        credentials = flow.run_local_server(port=0)

        with open(credentials_file, "w") as file:
            json.dump(json.loads(credentials.to_json()), file)

    youtube = googleapiclient.discovery.build(
        "youtube", api_version, credentials=credentials)
    return youtube


def get_liked_videos(youtube):
    liked_videos = []
    page_token = None

    while True:
        request = youtube.videos().list(
            part="id,snippet,statistics,contentDetails",
            myRating="like",
            maxResults=50,
            pageToken=page_token
        )
        response = request.execute()

        for item in response["items"]:
            title = item["snippet"]["title"]
            url = f"https://www.youtube.com/watch?v={item['id']}"
            views = int(item["statistics"]["viewCount"])
            likes = int(item["statistics"].get("likeCount", 0))

            topic_ids = item.get("topicDetails", {}).get(
                "topicIds", []) if "topicDetails" in item else []

            category_id = item["snippet"]["categoryId"]

            if category_id != "10":
                liked_videos.append((title, url, views, likes))
            else:
                print(f"Excluding YouTube Music video: {title} ({url})")

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return liked_videos


def create_database():
    conn = sqlite3.connect("liked_videos.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS videos
                   (title TEXT, url TEXT UNIQUE, views INTEGER, likes INTEGER)''')
    conn.commit()
    return conn


def clear_database(conn):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM videos")
    conn.commit()


def upsert_to_database(conn, liked_videos):
    cursor = conn.cursor()
    for title, url, views, likes in liked_videos:
        cursor.execute(
            "SELECT title, url, views, likes FROM videos WHERE url=?", (url,))
        existing_record = cursor.fetchone()

        if existing_record:
            existing_title, existing_url, existing_views, existing_likes = existing_record
            changes = []

            if title != existing_title:
                changes.append(f"Title: '{existing_title}' -> '{title}'")
            if views != existing_views:
                changes.append(f"Views: {existing_views} -> {views}")
            if likes != existing_likes:
                changes.append(f"Likes: {existing_likes} -> {likes}")

            if changes:
                print(f"Updating record for video '{title}' ({url}):")
                for change in changes:
                    print(f"  {change}")

        cursor.execute("""
            INSERT OR REPLACE INTO videos (title, url, views, likes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
            title=excluded.title, views=excluded.views, likes=excluded.likes""",
                       (title, url, views, likes))
        conn.commit()


def print_all_videos(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos")
    rows = cursor.fetchall()

    print("\nAll liked videos stored in the database:")
    for row in rows:
        title, url, views, likes = row
        print(f"\nTitle: {title}")
        print(f"URL: {url}")
        print(f"Views: {views}")
        print(f"Likes: {likes}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    youtube = authenticate()
    liked_videos = get_liked_videos(youtube)
    conn = create_database()

    clear_database(conn)  # Clear the database before adding new records
    upsert_to_database(conn, liked_videos)  # Upsert records based on the URL

    # print_all_videos(conn)
    conn.close()

    print(f"\nFound {len(liked_videos)} liked videos.")
    print("Data saved in liked_videos.db")

    #for title, url, views, likes in liked_videos:
    #    webbrowser.open_new_tab(url)


if __name__ == "__main__":
    main()
