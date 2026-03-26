import os
import sys
import re
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import fitz
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

CONFLUENCE_URL = os.getenv("CONFLUENCE_URL", "")
CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL", "")
CONFLUENCE_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", "")

AUTH = (CONFLUENCE_EMAIL, CONFLUENCE_TOKEN)
HEADERS = {"Accept": "application/json"}


def extract_pdf_text(pdf_bytes):
    text_parts = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts).strip()


def describe_image_groq(image_bytes, filename=""):
    try:
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        ext = filename.lower().split(".")[-1] if filename else "jpeg"
        mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
        mime = mime_map.get(ext, "image/jpeg")
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": "Describe this image in detail. Focus on any text, diagrams, charts, or important visual information."}
                ]
            }],
            max_tokens=512
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Image: {filename} - could not describe: {e}]"


def fetch_url_content(url, max_chars=3000):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return f"[Could not fetch {url}: HTTP {resp.status_code}]"
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text[:max_chars]
    except Exception as e:
        return f"[Could not fetch {url}: {e}]"


def get_page_attachments(page_id):
    url = f"{CONFLUENCE_URL}/wiki/rest/api/content/{page_id}/child/attachment"
    try:
        resp = requests.get(url, auth=AUTH, headers=HEADERS)
        if resp.status_code != 200:
            return []
        results = resp.json().get("results", [])
        attachments = []
        for r in results:
            attachments.append({
                "id": r["id"],
                "title": r["title"],
                "media_type": r["metadata"].get("mediaType", ""),
                "download_url": CONFLUENCE_URL.rstrip("/") + "/wiki" + r["_links"]["download"]
            })
        return attachments
    except Exception:
        return []


def extract_attachment_content(attachment):
    media_type = attachment["media_type"]
    title = attachment["title"]
    download_url = attachment["download_url"]
    try:
        resp = requests.get(download_url, auth=AUTH)
        if resp.status_code != 200:
            return f"[Could not download attachment: {title}]"
        raw = resp.content
        if "pdf" in media_type or title.lower().endswith(".pdf"):
            text = extract_pdf_text(raw)
            return f"[PDF: {title}]\n{text}"
        elif media_type.startswith("image/") or any(title.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
            desc = describe_image_groq(raw, title)
            return f"[Image: {title}]\n{desc}"
        else:
            return f"[Attachment: {title}]\n{raw.decode('utf-8', errors='ignore')[:2000]}"
    except Exception as e:
        return f"[Attachment: {title} - error: {e}]"


def extract_all_attachments(page_id):
    attachments = get_page_attachments(page_id)
    if not attachments:
        return ""
    parts = [extract_attachment_content(att) for att in attachments]
    return "\n\n".join(parts)


def extract_links_from_html(html_body):
    soup = BeautifulSoup(html_body, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") or href.startswith("/wiki"):
            links.append(href)
    return list(set(links))


def resolve_link_content(href, max_chars=2000):
    if href.startswith("/wiki"):
        full_url = CONFLUENCE_URL + href
        try:
            resp = requests.get(full_url, auth=AUTH, headers={"Accept": "text/html"})
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            return f"[Linked page: {full_url}]\n{text[:max_chars]}"
        except Exception as e:
            return f"[Could not resolve internal link {href}: {e}]"
    else:
        content = fetch_url_content(href, max_chars)
        return f"[External URL: {href}]\n{content}"