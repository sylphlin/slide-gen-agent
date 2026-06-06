import os
import time
import json
from google.adk.tools.tool_context import ToolContext

try:
    from ..config import CONFIG
    from ..tools.file_manager import get_topic_slug
except ImportError:
    from config import CONFIG
    from tools.file_manager import get_topic_slug


def _get_sa_email() -> str:
    """Fetches the current service account email from the GCE metadata server."""
    import urllib.request
    req = urllib.request.Request(
        'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email',
        headers={'Metadata-Flavor': 'Google'}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.read().decode()


def _get_drive_service_as_user(user_email: str):
    """Returns a Drive v3 service impersonating user_email via DWD.

    Uses IAM Credentials signJwt API — no service account key file required.
    The service account must have roles/iam.serviceAccountTokenCreator on itself
    and Domain-Wide Delegation configured in Google Workspace Admin Console.
    """
    import urllib.request
    import urllib.parse
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    import google.auth
    import google.auth.transport.requests

    SCOPES = ['https://www.googleapis.com/auth/drive.file']

    # Step 1 — Refresh ADC token (Compute Engine metadata, no key needed)
    adc_creds, _ = google.auth.default()
    adc_creds.refresh(google.auth.transport.requests.Request())

    sa_email = _get_sa_email()

    # Step 2 — Build DWD JWT payload
    now = int(time.time())
    jwt_payload = json.dumps({
        "iss": sa_email,
        "sub": user_email,       # DWD: act as this user
        "scope": " ".join(SCOPES),
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    })

    # Step 3 — Sign JWT via IAM Credentials API (keyless)
    sign_body = json.dumps({"payload": jwt_payload}).encode()
    sign_req = urllib.request.Request(
        f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{sa_email}:signJwt",
        data=sign_body,
        headers={
            "Authorization": f"Bearer {adc_creds.token}",
            "Content-Type": "application/json",
        },
        method="POST"
    )
    with urllib.request.urlopen(sign_req, timeout=30) as resp:
        signed_jwt = json.loads(resp.read())["signedJwt"]

    # Step 4 — Exchange signed JWT for user access token
    token_body = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": signed_jwt,
    }).encode()
    token_req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=token_body,
        method="POST"
    )
    with urllib.request.urlopen(token_req, timeout=30) as resp:
        access_token = json.loads(resp.read())["access_token"]

    return build('drive', 'v3', credentials=Credentials(token=access_token))


def _get_or_create_folder(service, folder_name: str) -> str:
    """Returns the folder ID in the user's Drive, creating it if needed."""
    results = service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields='files(id)',
        spaces='drive'
    ).execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
    folder = service.files().create(
        body={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'},
        fields='id'
    ).execute()
    return folder['id']


def _get_user_email(tool_context: ToolContext) -> str | None:
    try:
        user_id = tool_context._invocation_context.user_id
        if user_id and '@' in str(user_id):
            return user_id
    except AttributeError:
        pass
    return None


async def export_to_google_slides(session_path: str, tool_context: ToolContext) -> str:
    """Uploads the generated PPTX to the current user's Google Drive as a Google Slides
    presentation in their 'slide-gen-agent' folder. The user is the file owner.

    Uses keyless DWD via IAM Credentials signJwt — no service account key file needed.
    Requires: Drive API enabled, DWD configured in Google Workspace Admin,
    and roles/iam.serviceAccountTokenCreator granted to the service account on itself.

    Args:
        session_path: The absolute session path returned by initialize_session
        tool_context: The tool context injected by the framework
    """
    user_email = _get_user_email(tool_context)
    if not user_email:
        return (
            "Error: Could not determine user email from session. "
            "Google Slides export requires Gemini Enterprise authentication."
        )

    slug = get_topic_slug(session_path)
    pptx_path = os.path.join(session_path, f"{slug}.pptx")

    if not os.path.exists(pptx_path):
        return "Error: PPTX file not found. Please run the PPTX export first."

    try:
        from googleapiclient.http import MediaFileUpload

        folder_name = CONFIG.get('DRIVE_FOLDER_NAME', 'slide-gen-agent')
        service = _get_drive_service_as_user(user_email)
        folder_id = _get_or_create_folder(service, folder_name)

        file_metadata = {
            'name': slug,
            'mimeType': 'application/vnd.google-apps.presentation',
            'parents': [folder_id],
        }
        media = MediaFileUpload(
            pptx_path,
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            resumable=True
        )
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,webViewLink'
        ).execute()

        slides_url = file['webViewLink']
        return (
            f"Google Slides ready — open here: {slides_url}\n"
            f"Saved to your Drive: My Drive / {folder_name} / {slug}"
        )

    except Exception as e:
        return f"Failed to export to Google Slides: {str(e)}"
