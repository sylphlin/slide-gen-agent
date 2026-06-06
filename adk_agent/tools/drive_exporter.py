import os
import json
from google.adk.tools.tool_context import ToolContext

try:
    from ..config import CONFIG
    from ..tools.file_manager import get_topic_slug
except ImportError:
    from config import CONFIG
    from tools.file_manager import get_topic_slug


def _get_drive_service_as_user(user_email: str):
    """Returns a Drive v3 service impersonating user_email via Domain-Wide Delegation."""
    key_json_str = CONFIG.get('DRIVE_SERVICE_ACCOUNT_KEY')
    if not key_json_str:
        raise RuntimeError(
            "DRIVE_SERVICE_ACCOUNT_KEY is not set. "
            "Store the service account key JSON in Secret Manager and inject it as this env var."
        )
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    key_info = json.loads(key_json_str)
    creds = service_account.Credentials.from_service_account_info(
        key_info,
        scopes=['https://www.googleapis.com/auth/drive.file']
    ).with_subject(user_email)

    return build('drive', 'v3', credentials=creds)


def _get_or_create_folder(service, folder_name: str) -> str:
    """Returns the folder ID in the impersonated user's Drive, creating it if needed."""
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
    Requires Domain-Wide Delegation configured on the service account.

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
