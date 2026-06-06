import os
from google.adk.tools.tool_context import ToolContext

try:
    from ..config import CONFIG
    from ..tools.file_manager import get_topic_slug
except ImportError:
    from config import CONFIG
    from tools.file_manager import get_topic_slug


def _get_drive_service():
    import google.auth
    from googleapiclient.discovery import build
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/drive.file'])
    return build('drive', 'v3', credentials=creds)


def _get_or_create_folder(service, folder_name: str) -> str:
    """Returns the ID of the named Drive folder, creating it if it doesn't exist."""
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
    """Uploads the generated PPTX to Google Drive as a Google Slides presentation
    in the configured folder (default: 'slide-gen-agent'), then shares it with
    the current user as editor.

    Args:
        session_path: The absolute session path returned by initialize_session
        tool_context: The tool context injected by the framework
    """
    slug = get_topic_slug(session_path)
    pptx_path = os.path.join(session_path, f"{slug}.pptx")

    if not os.path.exists(pptx_path):
        return "Error: PPTX file not found. Please run the PPTX export first."

    try:
        from googleapiclient.http import MediaFileUpload

        folder_name = CONFIG.get('DRIVE_FOLDER_NAME', 'slide-gen-agent')
        service = _get_drive_service()
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
            fields='id,webViewLink',
            supportsAllDrives=True
        ).execute()

        file_id = file['id']
        slides_url = file['webViewLink']

        user_email = _get_user_email(tool_context)
        if user_email:
            service.permissions().create(
                fileId=file_id,
                body={'type': 'user', 'role': 'writer', 'emailAddress': user_email},
                fields='id',
                sendNotificationEmail=False,
                supportsAllDrives=True
            ).execute()
            return f"Google Slides ready — open here: {slides_url}\nShared with {user_email} as editor."

        return f"Google Slides ready — open here: {slides_url}"

    except Exception as e:
        return f"Failed to export to Google Slides: {str(e)}"
