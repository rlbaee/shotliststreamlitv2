import os
import json
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]
ROOT_FOLDER_NAME = "PAPSID 1-5 hooajad"
CACHE_FILE = "drive_cache.json"


def get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds


def get_folder_id(service, folder_name):
    res = service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)"
    ).execute()
    folders = res.get("files", [])
    return folders[0]["id"] if folders else None


def fetch_drive_tree(service, folder_id, progress=None):
    """Recursively fetch all files and folders from Google Drive."""
    items = []
    query = f"'{folder_id}' in parents and trashed=false"
    page_token = None
    while True:
        res = service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, parents)",
            pageToken=page_token
        ).execute()
        for f in res.get("files", []):
            items.append(f)
            if f["mimeType"] == "application/vnd.google-apps.folder":
                items.extend(fetch_drive_tree(service, f["id"], progress))
            if progress is not None:
                progress.progress(len(items))
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    return items


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_cache(data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def search_files(cached_files, query):
    query_lower = query.lower()
    return [f for f in cached_files if query_lower in f["name"].lower()]


# --------------------------
# STREAMLIT UI
# --------------------------
st.set_page_config(page_title="Drive Explorer", layout="wide")

st.title("📂 Google Drive Explorer")
st.markdown("Search and browse your cached Google Drive files.")

# Load credentials
creds = get_credentials()
service = build("drive", "v3", credentials=creds)
root_id = get_folder_id(service, ROOT_FOLDER_NAME)

if not root_id:
    st.error(f"Folder '{ROOT_FOLDER_NAME}' not found.")
    st.stop()

# Load or fetch cache
cache = load_cache()
if cache:
    st.info(f"Loaded {len(cache)} files from cache.")
else:
    st.info("Cache not found, fetching from Drive...")
    progress_bar = st.progress(0)
    cache = fetch_drive_tree(service, root_id, progress=progress_bar)
    save_cache(cache)
    st.success(f"Fetched {len(cache)} files and saved cache.")

# Search box
query = st.text_input("🔍 Search files by name:")
if query:
    results = search_files(cache, query)
    st.write(f"Found {len(results)} files matching '{query}':")
    for f in results:
        st.markdown(f"📄 **{f['name']}**")
