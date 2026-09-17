import re
import httpx

# Supported domains pre-check
TERABOX_REGEX = re.compile(r'https?://(?:www\.)?(terabox\.com|teraboxapp\.com|terasharelink\.com|1024tera\.com|teraboxlink\.com)/[a-zA-Z0-9_-]+')

async def is_valid_terabox_link(url: str) -> bool:
    return bool(TERABOX_REGEX.search(url))

async def fetch_media_info(url: str):
    """
    TODO: Replace this mock implementation with your actual TeraBox API Endpoint.
    Example: httpx.get("YOUR_API_URL", params={"url": url})
    """
    # Mock Data for architecture
    return {
        "ok": True,
        "file_name": "Example_Video.mp4",
        "file_size": 850 * 1024 * 1024, # 850 MB in bytes
        "download_url": "https://example.com/direct_link.mp4",
        "is_video": True
    }
