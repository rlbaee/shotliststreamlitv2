from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Start OAuth flow
flow = InstalledAppFlow.from_client_secrets_file("credentials.json", scopes=SCOPES)
creds = flow.run_local_server(port=0)  # 0 = random free port to avoid conflicts

# Save credentials to token.json
with open("token.json", "w") as token_file:
    token_file.write(creds.to_json())

print("✅ Authentication successful. 'token.json' created.")
