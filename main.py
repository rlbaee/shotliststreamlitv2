import os
import io
import json
import datetime
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

# --------------------------
# CONFIG
# --------------------------
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
ROOT_FOLDER_NAME = "PAPSID 1-5 hooajad"
CACHE_FILE = "drive_cache.json"

# --------------------------
# GOOGLE DRIVE AUTH
# --------------------------
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

# --------------------------
# FETCH FILE TREE
# --------------------------
def fetch_drive_tree(service, folder_id, progress=None):
    items = []
    query = f"'{folder_id}' in parents and trashed=false"
    page_token = None
    while True:
        res = service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, parents, webViewLink)",
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

# --------------------------
# SEARCH
# --------------------------
def search_files(cached_files, name_query="", date_query=None, use_date=True):
    results = []
    name_query_lower = name_query.lower()
    for f in cached_files:
        match_name = name_query_lower in f["name"].lower()
        match_date = True
        if use_date and date_query:
            match_date = date_query in f["name"]
        if match_name and match_date:
            results.append(f)
    return results

# --------------------------
# DOWNLOAD
# --------------------------
def download_file(service, file_id, mimeType):
    try:
        if mimeType == "application/vnd.google-apps.document":
            request = service.files().export_media(fileId=file_id, mimeType="application/pdf")
        elif mimeType == "application/vnd.google-apps.spreadsheet":
            request = service.files().export_media(fileId=file_id, mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif mimeType == "application/vnd.google-apps.presentation":
            request = service.files().export_media(fileId=file_id, mimeType="application/pdf")
        else:
            request = service.files().get_media(fileId=file_id)

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        return fh.read()
    except HttpError as e:
        st.warning(f"Cannot download '{file_id}': {e}")
        return None

# --------------------------
# STREAMLIT UI
# --------------------------
st.set_page_config(page_title="Drive Explorer", layout="wide")
st.markdown("<h1 style='text-align:center;'>📂 Your Google Drive Explorer</h1>", unsafe_allow_html=True)
st.markdown("---")

# Auth
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

# Search options (inline, not sidebar)
st.markdown("### Search Options")
col1, col2, col3 = st.columns([3,1,1])
with col1:
    name_query = st.text_input("File name contains:", "")
with col2:
    use_date = st.checkbox("Filter by date in name", value=True)
with col3:
    selected_date = st.date_input("Select date", value=datetime.date.today())

date_str = selected_date.strftime("%d.%m.%Y")

# Search
results = search_files(cache, name_query, date_query=date_str, use_date=use_date)
st.markdown(f"### Found {len(results)} files")

# Display results as cards
for f in results:
    st.markdown("<div style='padding:15px; border:1px solid #ddd; border-radius:10px; margin-bottom:10px;'>", unsafe_allow_html=True)
    col1, col2 = st.columns([4,1])
    with col1:
        st.markdown(f"📄 <b>{f['name']}</b>", unsafe_allow_html=True)
        if "webViewLink" in f:
            st.markdown(f"<a href='{f['webViewLink']}' target='_blank'>Open in Drive</a>", unsafe_allow_html=True)
    with col2:
        file_bytes = download_file(service, f["id"], f["mimeType"])
        if file_bytes:
            st.download_button(
                label="⬇ Download",
                data=file_bytes,
                file_name=f["name"],
                mime="application/octet-stream",
                key=f["id"]
            )
        if "webViewLink" in f:
            st.markdown(f"<a href='{f['webViewLink']}' target='_blank'>Share</a>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
