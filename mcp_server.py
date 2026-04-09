
# import os
# import sys
# import re
# import io
# import base64

# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# import requests
# from bs4 import BeautifulSoup
# from dotenv import load_dotenv
# from history_store import save_url

# load_dotenv()

# CONFLUENCE_URL   = os.getenv("CONFLUENCE_URL", "")
# CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL", "")
# CONFLUENCE_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", "")
# SPACE_KEY        = os.getenv("CONFLUENCE_SPACE_KEY", "AKB")
# GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")
# GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN", "")   # optional — raises rate limits

# AUTH    = (CONFLUENCE_EMAIL, CONFLUENCE_TOKEN)
# HEADERS = {"Accept": "application/json"}


# # ── Confluence REST helpers ────────────────────────────────────

# def _get(path, params=None):
#     url  = f"{CONFLUENCE_URL}/wiki/rest/api/{path}"
#     resp = requests.get(url, auth=AUTH, headers=HEADERS, params=params or {})
#     resp.raise_for_status()
#     return resp.json()

# def get_page_by_id(page_id):
#     try:
#         return _get(f"content/{page_id}", {"expand": "body.storage,version,title"})
#     except Exception:
#         return None

# def search_pages(query, limit=5):
#     try:
#         data = _get("content/search", {
#             "cql":    f'space="{SPACE_KEY}" AND text~"{query}" AND type=page',
#             "limit":  limit,
#             "expand": "body.storage,title,version",
#         })
#         return data.get("results", [])
#     except Exception:
#         return []

# def list_space_pages(limit=50):
#     try:
#         data = _get("content", {"spaceKey": SPACE_KEY, "type": "page", "limit": limit})
#         return [{"id": r["id"], "title": r["title"]} for r in data.get("results", [])]
#     except Exception:
#         return []

# def get_page_by_title(title):
#     try:
#         data = _get("content", {
#             "spaceKey": SPACE_KEY, "title": title,
#             "expand": "body.storage,version,title", "limit": 1,
#         })
#         results = data.get("results", [])
#         if results:
#             return results[0]
#     except Exception:
#         pass
#     results = search_pages(title, limit=3)
#     return results[0] if results else None


# # ── WRITE: Create a new Confluence page ───────────────────────

# def create_page(title: str, body_html: str, parent_id: str = None) -> dict:
#     """
#     Creates a new page in the Confluence space.
#     body_html : Confluence storage-format HTML
#     parent_id : optional page ID to nest this page under
#     Returns   : {"success": True,  "id": ..., "url": ..., "title": ...}
#               | {"success": False, "error": ...}
#     """
#     payload = {
#         "type":  "page",
#         "title": title,
#         "space": {"key": SPACE_KEY},
#         "body": {
#             "storage": {
#                 "value":          body_html,
#                 "representation": "storage",
#             }
#         },
#     }
#     if parent_id:
#         payload["ancestors"] = [{"id": parent_id}]

#     try:
#         resp = requests.post(
#             f"{CONFLUENCE_URL}/wiki/rest/api/content",
#             auth=AUTH,
#             headers={"Content-Type": "application/json", "Accept": "application/json"},
#             json=payload,
#             timeout=30,
#         )
#         resp.raise_for_status()
#         data     = resp.json()
#         page_id  = data["id"]
#         page_url = f"{CONFLUENCE_URL}/wiki/spaces/{SPACE_KEY}/pages/{page_id}"
#         print(f"  [WRITE] Page created: '{title}' → {page_url}")
#         save_url(page_url, title, "confluence", SPACE_KEY)
#         return {"success": True, "id": page_id, "url": page_url, "title": title}
#     except requests.HTTPError as e:
#         detail = ""
#         try:
#             detail = e.response.json().get("message", e.response.text[:300])
#         except Exception:
#             pass
#         print(f"  [WRITE] Create failed: {detail}")
#         return {"success": False, "error": detail}
#     except Exception as e:
#         print(f"  [WRITE] Create failed: {e}")
#         return {"success": False, "error": str(e)}


# # ── WRITE: Update an existing Confluence page ─────────────────

# def update_page(page_id: str, title: str, body_html: str) -> dict:
#     """
#     Replaces the content of an existing Confluence page (auto-increments version).
#     Returns: {"success": True,  "url": ..., "title": ...}
#            | {"success": False, "error": ...}
#     """
#     try:
#         current = _get(f"content/{page_id}", {"expand": "version"})
#         version = current["version"]["number"] + 1
#     except Exception as e:
#         return {"success": False, "error": f"Could not fetch page version: {e}"}

#     payload = {
#         "type":    "page",
#         "title":   title,
#         "version": {"number": version},
#         "body": {
#             "storage": {
#                 "value":          body_html,
#                 "representation": "storage",
#             }
#         },
#     }

#     try:
#         resp = requests.put(
#             f"{CONFLUENCE_URL}/wiki/rest/api/content/{page_id}",
#             auth=AUTH,
#             headers={"Content-Type": "application/json", "Accept": "application/json"},
#             json=payload,
#             timeout=30,
#         )
#         resp.raise_for_status()
#         page_url = f"{CONFLUENCE_URL}/wiki/spaces/{SPACE_KEY}/pages/{page_id}"
#         print(f"  [WRITE] Page updated: '{title}' v{version} → {page_url}")
#         return {"success": True, "url": page_url, "title": title}
#     except requests.HTTPError as e:
#         detail = ""
#         try:
#             detail = e.response.json().get("message", e.response.text[:300])
#         except Exception:
#             pass
#         print(f"  [WRITE] Update failed: {detail}")
#         return {"success": False, "error": detail}
#     except Exception as e:
#         print(f"  [WRITE] Update failed: {e}")
#         return {"success": False, "error": str(e)}


# # ── GitHub repo reader ─────────────────────────────────────────
# # Uses github.com web pages + raw.githubusercontent.com for file content.
# # Avoids api.github.com which is often blocked by corporate proxies.

# _READABLE_EXTENSIONS = {
#     ".md", ".mdx", ".rst", ".txt",
#     ".py", ".js", ".ts", ".jsx", ".tsx",
#     ".java", ".go", ".rb", ".php", ".cs", ".cpp", ".c", ".h",
#     ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg",
#     ".sh", ".bash", ".sql", ".env.example",
# }

# _SKIP_DIRS = {
#     "node_modules", ".git", "dist", "build", "__pycache__",
#     ".pytest_cache", "venv", ".venv", "coverage", ".nyc_output",
#     "vendor", ".idea", ".vscode",
# }

# def _should_read_github_file(path: str) -> bool:
#     parts = path.lower().split("/")
#     for part in parts[:-1]:
#         if part in _SKIP_DIRS:
#             return False
#     name = parts[-1]
#     _, ext = os.path.splitext(name)
#     return (ext.lower() in _READABLE_EXTENSIONS
#             or name in {"dockerfile", "makefile", "procfile", "gemfile", "rakefile"})


# def _web_get(url: str, timeout: int = 15, headers: dict = None) -> requests.Response:
#     """
#     HTTP GET that tries system proxy env vars first, then falls back to verify=False.
#     Handles corporate proxies that block or intercept SSL.
#     """
#     import urllib3
#     h = {"User-Agent": "Mozilla/5.0 (compatible; ConfluenceBot/1.0)"}
#     if headers:
#         h.update(headers)

#     # Try 1: normal request (uses system proxy from env if set)
#     try:
#         return requests.get(url, headers=h, timeout=timeout, verify=True)
#     except Exception as e1:
#         err = str(e1).lower()
#         if not any(k in err for k in ("ssl", "eof", "certificate", "proxy", "connect")):
#             raise  # non-SSL error — don't suppress

#     # Try 2: skip SSL verification (corporate proxy re-signing certs)
#     try:
#         urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
#         print(f"  [GITHUB] SSL issue — retrying with verify=False")
#         return requests.get(url, headers=h, timeout=timeout, verify=False)
#     except Exception as e2:
#         raise Exception(f"Both SSL attempts failed. Original: {e1} | No-verify: {e2}")


# def _scrape_github_file_list(owner: str, repo: str, branch: str = "main",
#                               path: str = "") -> list:
#     """
#     Scrapes the GitHub web page to list files in a directory.
#     Returns list of {"path": str, "type": "file"|"dir"} dicts.
#     """
#     url  = f"https://github.com/{owner}/{repo}/tree/{branch}/{path}".rstrip("/")
#     try:
#         resp = _web_get(url, timeout=15)
#         soup = BeautifulSoup(resp.text, "html.parser")
#         items = []
#         # GitHub renders file rows as <a> tags with aria-label containing file names
#         for tag in soup.select("a[href*='blob'], a[href*='tree']"):
#             href = tag.get("href", "")
#             if f"/{owner}/{repo}/blob/{branch}/" in href:
#                 file_path = href.split(f"/{owner}/{repo}/blob/{branch}/", 1)[-1]
#                 if file_path and file_path not in [i["path"] for i in items]:
#                     items.append({"path": file_path, "type": "file"})
#             elif f"/{owner}/{repo}/tree/{branch}/" in href:
#                 dir_path = href.split(f"/{owner}/{repo}/tree/{branch}/", 1)[-1]
#                 if dir_path and dir_path not in [i["path"] for i in items] and dir_path != path:
#                     items.append({"path": dir_path, "type": "dir"})
#         return items
#     except Exception as e:
#         print(f"  [GITHUB] Could not scrape file list for {path or 'root'}: {e}")
#         return []


# def _scrape_all_files(owner: str, repo: str, branch: str,
#                       max_files: int = 40) -> list:
#     """
#     Recursively walk the repo via web scraping to collect all readable file paths.
#     """
#     all_files = []
#     dirs_to_visit = [""]   # start from root
#     visited_dirs  = set()

#     while dirs_to_visit and len(all_files) < max_files * 2:
#         current_dir = dirs_to_visit.pop(0)
#         if current_dir in visited_dirs:
#             continue
#         visited_dirs.add(current_dir)

#         # Skip blocked dirs
#         parts = current_dir.lower().split("/")
#         if any(p in _SKIP_DIRS for p in parts):
#             continue

#         items = _scrape_github_file_list(owner, repo, branch, current_dir)
#         for item in items:
#             if item["type"] == "file" and _should_read_github_file(item["path"]):
#                 all_files.append(item["path"])
#             elif item["type"] == "dir":
#                 dirs_to_visit.append(item["path"])

#     return all_files


# def _fetch_raw_file(owner: str, repo: str, branch: str, path: str,
#                     max_chars: int = 3000) -> str:
#     """
#     Fetch raw file content from raw.githubusercontent.com.
#     Falls back to scraping the blob page if raw fails.
#     """
#     raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
#     try:
#         resp = _web_get(raw_url, timeout=15)
#         if resp.status_code == 200:
#             return resp.text[:max_chars]
#     except Exception as e:
#         print(f"  [GITHUB] raw.githubusercontent.com failed for {path}: {e}")

#     # Fallback: scrape blob page
#     blob_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"
#     try:
#         resp = _web_get(blob_url, timeout=15)
#         soup = BeautifulSoup(resp.text, "html.parser")
#         # GitHub renders code in <table> with line numbers or in a <code> block
#         code = soup.find("table", {"data-tagsearch-lang": True})
#         if code:
#             return code.get_text(separator="\n")[:max_chars]
#         raw_div = soup.find("div", {"id": "raw-url"})
#         if raw_div:
#             return soup.get_text(separator="\n")[:max_chars]
#     except Exception as e:
#         print(f"  [GITHUB] blob page scrape failed for {path}: {e}")

#     return ""


# def _scrape_repo_meta(owner: str, repo: str) -> dict:
#     """
#     Scrape repo metadata (description, default branch, language) from GitHub web page.
#     """
#     url = f"https://github.com/{owner}/{repo}"
#     try:
#         resp = _web_get(url, timeout=15)
#         soup = BeautifulSoup(resp.text, "html.parser")

#         # Description
#         desc_tag = soup.find("p", {"class": lambda c: c and "f4" in c})
#         description = desc_tag.get_text(strip=True) if desc_tag else ""

#         # Default branch — look for branch selector
#         branch = "main"
#         branch_btn = soup.find("span", {"class": lambda c: c and "branch" in str(c).lower()})
#         if not branch_btn:
#             # Try meta tags
#             for link in soup.find_all("link", {"rel": "canonical"}):
#                 pass  # just checking page loaded
#         # Try to find branch in page source
#         branch_match = re.search(r'"defaultBranch":"([^"]+)"', resp.text)
#         if branch_match:
#             branch = branch_match.group(1)
#         else:
#             # Try "main" then "master"
#             for b in ("main", "master", "develop"):
#                 test_url = f"https://github.com/{owner}/{repo}/tree/{b}"
#                 try:
#                     tr = _web_get(test_url, timeout=8)
#                     if tr.status_code == 200 and f"/tree/{b}" in tr.url:
#                         branch = b
#                         break
#                 except Exception:
#                     continue

#         # Language
#         lang_tag = soup.find("span", {"itemprop": "programmingLanguage"})
#         language = lang_tag.get_text(strip=True) if lang_tag else "Unknown"

#         print(f"  [GITHUB] Scraped meta: branch={branch} lang={language} desc={description[:60]}")
#         return {"description": description, "branch": branch, "language": language}

#     except Exception as e:
#         print(f"  [GITHUB] Meta scrape failed: {e} — using defaults")
#         return {"description": "", "branch": "main", "language": "Unknown"}


# def read_github_repo(repo_url: str, max_files: int = 40,
#                      max_chars_per_file: int = 3000) -> dict:
#     """
#     Reads a GitHub repository WITHOUT using api.github.com.
#     Uses github.com web pages + raw.githubusercontent.com instead,
#     which works even when corporate proxies block the GitHub API.

#     Strategy:
#       1. Scrape github.com/{owner}/{repo} for metadata + branch
#       2. Scrape file tree by walking directory pages
#       3. Fetch each file from raw.githubusercontent.com
#     """
#     m = re.search(r"github\.com[/:]([^/\s]+)/([^/\s#?]+)", repo_url)
#     if not m:
#         return {"error": f"Could not parse GitHub repo URL: {repo_url}"}

#     owner = m.group(1)
#     repo  = m.group(2).rstrip(".git")
#     print(f"  [GITHUB] Reading repo via web scrape: {owner}/{repo}")

#     # ── Step 1: Repo metadata ──
#     meta   = _scrape_repo_meta(owner, repo)
#     branch = meta["branch"]

#     # ── Step 2: File tree ──
#     print(f"  [GITHUB] Walking file tree (branch: {branch})...")
#     all_files = _scrape_all_files(owner, repo, branch, max_files=max_files)
#     print(f"  [GITHUB] Found {len(all_files)} readable files")

#     if not all_files:
#         # Last resort: try to at least get the README
#         print("  [GITHUB] No files scraped — trying README directly")
#         for readme_name in ("README.md", "readme.md", "README.rst", "README.txt"):
#             content = _fetch_raw_file(owner, repo, branch, readme_name, max_chars_per_file)
#             if content.strip():
#                 all_files = [readme_name]
#                 break

#     # ── Step 3: Prioritise and read files ──
#     def _priority(path):
#         name = path.lower()
#         if re.match(r"readme", name):              return 0
#         if "/" not in path:                         return 1
#         if name.startswith("docs/"):               return 2
#         if name.endswith((".yml", ".yaml", ".toml", ".json")): return 3
#         if name.startswith(("src/", "app/", "lib/")): return 4
#         return 5

#     all_files.sort(key=_priority)
#     selected = all_files[:max_files]
#     print(f"  [GITHUB] Reading {len(selected)} files from raw.githubusercontent.com...")

#     files_content = []
#     readme_text   = ""

#     for path in selected:
#         text = _fetch_raw_file(owner, repo, branch, path, max_chars_per_file)
#         if text.strip():
#             files_content.append({"path": path, "content": text})
#             if re.match(r"readme", path.lower()):
#                 readme_text = text
#             print(f"  [GITHUB] ✓ {path} ({len(text)} chars)")
#         else:
#             print(f"  [GITHUB] ✗ {path} (empty or failed)")

#     if not files_content:
#         return {"error": (
#             f"Could not read any files from {owner}/{repo}. "
#             "The repo may be private, or both github.com and raw.githubusercontent.com "
#             "are blocked by your corporate network. "
#             "Try setting HTTPS_PROXY in your .env file."
#         )}

#     return {
#         "owner":       owner,
#         "repo":        repo,
#         "description": meta["description"],
#         "language":    meta["language"],
#         "stars":       0,
#         "topics":      [],
#         "files":       files_content,
#         "readme":      readme_text,
#         "error":       None,
#     }


# # ── AUTO PDF extractor ─────────────────────────────────────────

# def _extract_pdf_text(pdf_bytes: bytes) -> str:
#     try:
#         import fitz
#         doc  = fitz.open(stream=pdf_bytes, filetype="pdf")
#         text = "\n".join(page.get_text() for page in doc)
#         doc.close()
#         if text.strip():
#             print(f"  [PDF] Extracted {len(text)} chars via PyMuPDF")
#             return text.strip()
#         print("  [PDF] PyMuPDF returned empty — trying pdfplumber")
#     except ImportError:
#         print("  [PDF] PyMuPDF not installed — trying pdfplumber")
#     except Exception as e:
#         print(f"  [PDF] PyMuPDF failed: {e} — trying pdfplumber")

#     try:
#         import pdfplumber
#         with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
#             pages_text = []
#             for i, p in enumerate(pdf.pages):
#                 t = p.extract_text() or ""
#                 pages_text.append(t)
#                 print(f"  [PDF] pdfplumber page {i+1}: {len(t)} chars")
#             result = "\n".join(pages_text).strip()
#             print(f"  [PDF] Extracted {len(result)} chars via pdfplumber")
#             return result
#     except ImportError:
#         msg = "[PDF extraction failed: run: pip install pymupdf pdfplumber]"
#         print(f"  [PDF] ERROR: {msg}")
#         return msg
#     except Exception as e:
#         msg = f"[PDF extraction failed: {e}]"
#         print(f"  [PDF] ERROR: {msg}")
#         return msg


# # ── AUTO Image describer ───────────────────────────────────────

# def _describe_image(image_bytes: bytes, mime: str = "image/jpeg") -> str:
#     if not GROQ_API_KEY:
#         return "[Image description skipped: GROQ_API_KEY not set]"
#     try:
#         b64 = base64.b64encode(image_bytes).decode()
#         r   = requests.post(
#             "https://api.groq.com/openai/v1/chat/completions",
#             headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
#             json={
#                 "model": "meta-llama/llama-4-scout-17b-16e-instruct",
#                 "messages": [{"role": "user", "content": [
#                     {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
#                     {"type": "text", "text": (
#                         "Describe this image in full detail. Include any text, numbers, "
#                         "charts, diagrams, tables or important visual information."
#                     )},
#                 ]}],
#                 "max_tokens": 600,
#             },
#             timeout=30,
#         )
#         r.raise_for_status()
#         return r.json()["choices"][0]["message"]["content"].strip()
#     except Exception as e:
#         return f"[Image description failed: {e}]"


# # ── AUTO URL fetcher ───────────────────────────────────────────

# def _fetch_url_text(url: str, max_chars: int = 2000) -> str:
#     try:
#         r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
#         r.raise_for_status()
#         soup = BeautifulSoup(r.text, "html.parser")
#         for tag in soup(["script", "style", "nav", "footer", "header"]):
#             tag.decompose()
#         return re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n")).strip()[:max_chars]
#     except Exception as e:
#         return f"[URL fetch failed: {e}]"


# # ── AUTO attachment extractor ──────────────────────────────────

# def _auto_extract_attachments(page_id: str) -> str:
#     try:
#         data = _get(f"content/{page_id}/child/attachment", {"limit": 20})
#     except Exception:
#         return ""

#     results = data.get("results", [])
#     if not results:
#         print(f"  [AUTO] No attachments on page {page_id}")
#         return ""

#     print(f"  [AUTO] Found {len(results)} attachment(s): {[a.get('title','?') for a in results]}")
#     sections = []

#     for att in results:
#         title   = att.get("title", "unnamed")
#         mime    = att.get("metadata", {}).get("mediaType", "")
#         dl_path = att.get("_links", {}).get("download", "")
#         dl_url  = f"{CONFLUENCE_URL}/wiki{dl_path}" if dl_path else None

#         print(f"  [AUTO] Processing: '{title}' | mime: {mime}")
#         if not dl_url:
#             continue

#         try:
#             raw = requests.get(dl_url, auth=AUTH, timeout=30).content
#             print(f"  [AUTO] Downloaded '{title}': {len(raw)} bytes")
#         except Exception as e:
#             sections.append(f"[Attachment '{title}': download failed — {e}]")
#             print(f"  [AUTO] Download FAILED for '{title}': {e}")
#             continue

#         if "pdf" in mime or title.lower().endswith(".pdf"):
#             text = _extract_pdf_text(raw)
#             sections.append(f"[PDF: {title}]\n{text[:6000]}")
#             print(f"  [AUTO] PDF '{title}' → context ({len(text)} chars)")

#         elif mime.startswith("image/") or any(
#             title.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")
#         ):
#             ext_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
#                        "png": "image/png",  "gif":  "image/gif", "webp": "image/webp"}
#             ext     = title.rsplit(".", 1)[-1].lower() if "." in title else ""
#             caption = _describe_image(raw, ext_map.get(ext, mime or "image/jpeg"))
#             sections.append(f"[Image: {title}]\n{caption}")
#             print(f"  [AUTO] Image '{title}' described ({len(caption)} chars)")

#         else:
#             sections.append(f"[Attachment: {title} — type: {mime}]")

#     return "\n\n".join(sections)


# # ── AUTO hyperlink extractor ───────────────────────────────────

# def _auto_extract_urls(html_body: str, page_url: str) -> str:
#     """
#     Extracts and fetches content from ALL links inside a Confluence page:
#       1. <ac:link><ri:page ri:content-title="..."/> -- internal Confluence page links (storage format)
#       2. <ac:link><ri:page ri:content-id="..."/>    -- internal links by page ID
#       3. <a href="...">                              -- regular hyperlinks (external or Confluence URL)
#     """
#     soup     = BeautifulSoup(html_body, "html.parser")
#     sections = []
#     seen     = set()

#     # ── 1. Confluence native <ac:link> macros ──────────────────────────────
#     # Confluence stores internal links as:
#     #   <ac:link><ri:page ri:content-title="Page Title" ri:space-key="KEY"/></ac:link>
#     for ac_link in soup.find_all("ac:link"):
#         ri_page = ac_link.find("ri:page")
#         if not ri_page:
#             continue

#         linked_title = ri_page.get("ri:content-title", "").strip()
#         linked_id    = ri_page.get("ri:content-id", "").strip()

#         if linked_title and linked_title not in seen:
#             seen.add(linked_title)
#             print(f"  [LINKS] Internal link by title: '{linked_title}'")
#             inner = get_page_by_title(linked_title)
#             if inner:
#                 inner_id   = inner["id"]
#                 inner_html = inner.get("body", {}).get("storage", {}).get("value", "")
#                 inner_text = re.sub(r"\n{3,}", "\n\n",
#                     BeautifulSoup(inner_html, "html.parser").get_text(separator="\n", strip=True))
#                 inner_url  = f"{CONFLUENCE_URL}/wiki/spaces/{SPACE_KEY}/pages/{inner_id}"
#                 att_text   = _auto_extract_attachments(inner_id)
#                 content    = inner_text[:3000] + (f"\n\n{att_text[:2000]}" if att_text else "")
#                 sections.append(
#                     f"[Linked Confluence Page: {inner.get('title', linked_title)}]\n"
#                     f"URL: {inner_url}\n{content}"
#                 )
#                 save_url(inner_url, inner.get("title", linked_title), "confluence", SPACE_KEY)
#             else:
#                 print(f"  [LINKS] Could not fetch linked page: '{linked_title}'")

#         elif linked_id and linked_id not in seen:
#             seen.add(linked_id)
#             print(f"  [LINKS] Internal link by ID: {linked_id}")
#             inner = get_page_by_id(linked_id)
#             if inner:
#                 inner_html = inner.get("body", {}).get("storage", {}).get("value", "")
#                 inner_text = re.sub(r"\n{3,}", "\n\n",
#                     BeautifulSoup(inner_html, "html.parser").get_text(separator="\n", strip=True))
#                 inner_url  = f"{CONFLUENCE_URL}/wiki/spaces/{SPACE_KEY}/pages/{linked_id}"
#                 att_text   = _auto_extract_attachments(linked_id)
#                 content    = inner_text[:3000] + (f"\n\n{att_text[:2000]}" if att_text else "")
#                 sections.append(
#                     f"[Linked Confluence Page: {inner.get('title', linked_id)}]\n"
#                     f"URL: {inner_url}\n{content}"
#                 )
#                 save_url(inner_url, inner.get("title", linked_id), "confluence", SPACE_KEY)

#     # ── 2. Standard <a href> links ─────────────────────────────────────────
#     for tag in soup.find_all("a", href=True):
#         href = tag["href"].strip()
#         if href.startswith(("#", "mailto:")):
#             continue
#         if href.startswith("/"):
#             href = f"{CONFLUENCE_URL}{href}"
#         if not href.startswith("http"):
#             continue
#         if href in seen or href == page_url:
#             continue
#         seen.add(href)

#         if CONFLUENCE_URL in href and "/pages/" in href:
#             m = re.search(r"/pages/(\d+)", href)
#             if m:
#                 inner = get_page_by_id(m.group(1))
#                 if inner:
#                     inner_html = inner.get("body", {}).get("storage", {}).get("value", "")
#                     inner_text = re.sub(r"\n{3,}", "\n\n",
#                         BeautifulSoup(inner_html, "html.parser").get_text(separator="\n", strip=True))
#                     att_text   = _auto_extract_attachments(inner["id"])
#                     content    = inner_text[:3000] + (f"\n\n{att_text[:2000]}" if att_text else "")
#                     sections.append(
#                         f"[Linked Confluence Page: {inner.get('title', href)}]\n"
#                         f"URL: {href}\n{content}"
#                     )
#                     save_url(href, inner.get("title", href), "confluence", SPACE_KEY)
#                     print(f"  [LINKS] Internal page via href: '{inner.get('title', href)}'")
#                     continue

#         print(f"  [LINKS] External URL: {href[:80]}")
#         content = _fetch_url_text(href, max_chars=1500)
#         sections.append(f"[Linked URL: {href}]\n{content}")
#         save_url(href, href, "external")

#     print(f"  [LINKS] Linked sections fetched: {len(sections)}")
#     return "\n\n".join(sections)


# # ── Main context builder ───────────────────────────────────────

# def build_page_context(page: dict, follow_links: bool = True) -> str:
#     page_id   = page["id"]
#     title     = page["title"]
#     html_body = page.get("body", {}).get("storage", {}).get("value", "")
#     page_url  = f"{CONFLUENCE_URL}/wiki/spaces/{SPACE_KEY}/pages/{page_id}"

#     save_url(page_url, title, "confluence", SPACE_KEY)

#     soup      = BeautifulSoup(html_body, "html.parser")
#     body_text = re.sub(r"\n{3,}", "\n\n",
#                        soup.get_text(separator="\n", strip=True))

#     sections = [
#         f"=== PAGE: {title} ===",
#         f"URL: {page_url}",
#         "",
#         "--- Page Content ---",
#         body_text,
#     ]

#     print(f"  [AUTO] Extracting attachments from '{title}'...")
#     att_text = _auto_extract_attachments(page_id)
#     sections += (["", "--- Attachments ---", att_text]
#                  if att_text else ["", "--- Attachments: none ---"])

#     url_text = ""
#     if follow_links:
#         print(f"  [AUTO] Fetching linked URLs from '{title}'...")
#         url_text = _auto_extract_urls(html_body, page_url)
#         sections += (["", "--- Linked Content ---", url_text]
#                      if url_text else ["", "--- Linked URLs: none ---"])

#     full = "\n".join(sections)
#     print(f"  [AUTO] Context ready: {len(full)} chars | body:{len(body_text)} att:{len(att_text)} links:{len(url_text)}")
#     return full


# # ── Public API ─────────────────────────────────────────────────

# def fetch_context_for_query(user_query: str) -> str:
#     results = search_pages(user_query, limit=3)
#     if results:
#         page = results[0]
#         if not page.get("body", {}).get("storage", {}).get("value"):
#             page = get_page_by_id(page["id"])
#         if page:
#             return build_page_context(page, follow_links=True)

#     all_pages = list_space_pages()
#     if not all_pages:
#         return "No pages found in the Confluence space."
#     page_list = "\n".join(f"- {p['title']} (id: {p['id']})" for p in all_pages)
#     return f"Available pages in space:\n{page_list}\n\nNo direct match for: {user_query}"


# def fetch_context_for_page_title(title: str) -> str:
#     page = get_page_by_title(title)
#     if not page:
#         return f"Page '{title}' not found in space {SPACE_KEY}."
#     return build_page_context(page, follow_links=True)





import os
import sys
import re
import io
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from history_store import save_url

load_dotenv()

CONFLUENCE_URL   = os.getenv("CONFLUENCE_URL", "")
CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL", "")
CONFLUENCE_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", "")
SPACE_KEY        = os.getenv("CONFLUENCE_SPACE_KEY", "AKB")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN", "")   # optional — raises rate limits

AUTH    = (CONFLUENCE_EMAIL, CONFLUENCE_TOKEN)
HEADERS = {"Accept": "application/json"}


# ── Confluence REST helpers ────────────────────────────────────

def _get(path, params=None):
    url  = f"{CONFLUENCE_URL}/wiki/rest/api/{path}"
    resp = requests.get(url, auth=AUTH, headers=HEADERS, params=params or {})
    resp.raise_for_status()
    return resp.json()

def get_page_by_id(page_id):
    try:
        return _get(f"content/{page_id}", {"expand": "body.storage,version,title"})
    except Exception:
        return None

def search_pages(query, limit=5):
    try:
        data = _get("content/search", {
            "cql":    f'space="{SPACE_KEY}" AND text~"{query}" AND type=page',
            "limit":  limit,
            "expand": "body.storage,title,version",
        })
        return data.get("results", [])
    except Exception:
        return []

def list_space_pages(limit=50):
    try:
        data = _get("content", {"spaceKey": SPACE_KEY, "type": "page", "limit": limit})
        pages = [{"id": r["id"], "title": r["title"]} for r in data.get("results", [])]
        if not pages:
            print(f"  [CONFLUENCE] list_space_pages returned 0 results for space '{SPACE_KEY}'")
            print(f"  [CONFLUENCE] Check CONFLUENCE_SPACE_KEY in your .env (current: '{SPACE_KEY}')")
        return pages
    except Exception as e:
        print(f"  [CONFLUENCE] list_space_pages FAILED: {e}")
        print(f"  [CONFLUENCE] Check CONFLUENCE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN in .env")
        return []

def get_page_by_title(title):
    try:
        data = _get("content", {
            "spaceKey": SPACE_KEY, "title": title,
            "expand": "body.storage,version,title", "limit": 1,
        })
        results = data.get("results", [])
        if results:
            return results[0]
    except Exception:
        pass
    results = search_pages(title, limit=3)
    return results[0] if results else None


# ── WRITE: Create a new Confluence page ───────────────────────

def create_page(title: str, body_html: str, parent_id: str = None) -> dict:
    """
    Creates a new page in the Confluence space.
    body_html : Confluence storage-format HTML
    parent_id : optional page ID to nest this page under
    Returns   : {"success": True,  "id": ..., "url": ..., "title": ...}
              | {"success": False, "error": ...}
    """
    payload = {
        "type":  "page",
        "title": title,
        "space": {"key": SPACE_KEY},
        "body": {
            "storage": {
                "value":          body_html,
                "representation": "storage",
            }
        },
    }
    if parent_id:
        payload["ancestors"] = [{"id": parent_id}]

    try:
        resp = requests.post(
            f"{CONFLUENCE_URL}/wiki/rest/api/content",
            auth=AUTH,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data     = resp.json()
        page_id  = data["id"]
        page_url = f"{CONFLUENCE_URL}/wiki/spaces/{SPACE_KEY}/pages/{page_id}"
        print(f"  [WRITE] Page created: '{title}' → {page_url}")
        save_url(page_url, title, "confluence", SPACE_KEY)
        return {"success": True, "id": page_id, "url": page_url, "title": title}
    except requests.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("message", e.response.text[:300])
        except Exception:
            pass
        print(f"  [WRITE] Create failed: {detail}")
        return {"success": False, "error": detail}
    except Exception as e:
        print(f"  [WRITE] Create failed: {e}")
        return {"success": False, "error": str(e)}


# ── WRITE: Update an existing Confluence page ─────────────────

def update_page(page_id: str, title: str, body_html: str) -> dict:
    """
    Replaces the content of an existing Confluence page (auto-increments version).
    Returns: {"success": True,  "url": ..., "title": ...}
           | {"success": False, "error": ...}
    """
    try:
        current = _get(f"content/{page_id}", {"expand": "version"})
        version = current["version"]["number"] + 1
    except Exception as e:
        return {"success": False, "error": f"Could not fetch page version: {e}"}

    payload = {
        "type":    "page",
        "title":   title,
        "version": {"number": version},
        "body": {
            "storage": {
                "value":          body_html,
                "representation": "storage",
            }
        },
    }

    try:
        resp = requests.put(
            f"{CONFLUENCE_URL}/wiki/rest/api/content/{page_id}",
            auth=AUTH,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        page_url = f"{CONFLUENCE_URL}/wiki/spaces/{SPACE_KEY}/pages/{page_id}"
        print(f"  [WRITE] Page updated: '{title}' v{version} → {page_url}")
        return {"success": True, "url": page_url, "title": title}
    except requests.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("message", e.response.text[:300])
        except Exception:
            pass
        print(f"  [WRITE] Update failed: {detail}")
        return {"success": False, "error": detail}
    except Exception as e:
        print(f"  [WRITE] Update failed: {e}")
        return {"success": False, "error": str(e)}


# ── GitHub repo reader ─────────────────────────────────────────
# Uses github.com web pages + raw.githubusercontent.com for file content.
# Avoids api.github.com which is often blocked by corporate proxies.

_READABLE_EXTENSIONS = {
    ".md", ".mdx", ".rst", ".txt",
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".go", ".rb", ".php", ".cs", ".cpp", ".c", ".h",
    ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg",
    ".sh", ".bash", ".sql", ".env.example",
}

_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "__pycache__",
    ".pytest_cache", "venv", ".venv", "coverage", ".nyc_output",
    "vendor", ".idea", ".vscode",
}

def _should_read_github_file(path: str) -> bool:
    parts = path.lower().split("/")
    for part in parts[:-1]:
        if part in _SKIP_DIRS:
            return False
    name = parts[-1]
    _, ext = os.path.splitext(name)
    return (ext.lower() in _READABLE_EXTENSIONS
            or name in {"dockerfile", "makefile", "procfile", "gemfile", "rakefile"})


def _web_get(url: str, timeout: int = 15, headers: dict = None) -> requests.Response:
    """
    HTTP GET that tries system proxy env vars first, then falls back to verify=False.
    Handles corporate proxies that block or intercept SSL.
    """
    import urllib3
    h = {"User-Agent": "Mozilla/5.0 (compatible; ConfluenceBot/1.0)"}
    if headers:
        h.update(headers)

    # Try 1: normal request (uses system proxy from env if set)
    try:
        return requests.get(url, headers=h, timeout=timeout, verify=True)
    except Exception as e1:
        err = str(e1).lower()
        if not any(k in err for k in ("ssl", "eof", "certificate", "proxy", "connect")):
            raise  # non-SSL error — don't suppress

    # Try 2: skip SSL verification (corporate proxy re-signing certs)
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        print(f"  [GITHUB] SSL issue — retrying with verify=False")
        return requests.get(url, headers=h, timeout=timeout, verify=False)
    except Exception as e2:
        raise Exception(f"Both SSL attempts failed. Original: {e1} | No-verify: {e2}")


def _scrape_github_file_list(owner: str, repo: str, branch: str = "main",
                              path: str = "") -> list:
    """
    Scrapes the GitHub web page to list files in a directory.
    Returns list of {"path": str, "type": "file"|"dir"} dicts.
    """
    url  = f"https://github.com/{owner}/{repo}/tree/{branch}/{path}".rstrip("/")
    try:
        resp = _web_get(url, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = []
        # GitHub renders file rows as <a> tags with aria-label containing file names
        for tag in soup.select("a[href*='blob'], a[href*='tree']"):
            href = tag.get("href", "")
            if f"/{owner}/{repo}/blob/{branch}/" in href:
                file_path = href.split(f"/{owner}/{repo}/blob/{branch}/", 1)[-1]
                if file_path and file_path not in [i["path"] for i in items]:
                    items.append({"path": file_path, "type": "file"})
            elif f"/{owner}/{repo}/tree/{branch}/" in href:
                dir_path = href.split(f"/{owner}/{repo}/tree/{branch}/", 1)[-1]
                if dir_path and dir_path not in [i["path"] for i in items] and dir_path != path:
                    items.append({"path": dir_path, "type": "dir"})
        return items
    except Exception as e:
        print(f"  [GITHUB] Could not scrape file list for {path or 'root'}: {e}")
        return []


def _scrape_all_files(owner: str, repo: str, branch: str,
                      max_files: int = 40) -> list:
    """
    Recursively walk the repo via web scraping to collect all readable file paths.
    """
    all_files = []
    dirs_to_visit = [""]   # start from root
    visited_dirs  = set()

    while dirs_to_visit and len(all_files) < max_files * 2:
        current_dir = dirs_to_visit.pop(0)
        if current_dir in visited_dirs:
            continue
        visited_dirs.add(current_dir)

        # Skip blocked dirs
        parts = current_dir.lower().split("/")
        if any(p in _SKIP_DIRS for p in parts):
            continue

        items = _scrape_github_file_list(owner, repo, branch, current_dir)
        for item in items:
            if item["type"] == "file" and _should_read_github_file(item["path"]):
                all_files.append(item["path"])
            elif item["type"] == "dir":
                dirs_to_visit.append(item["path"])

    return all_files


def _fetch_raw_file(owner: str, repo: str, branch: str, path: str,
                    max_chars: int = 3000) -> str:
    """
    Fetch raw file content from raw.githubusercontent.com.
    Falls back to scraping the blob page if raw fails.
    """
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    try:
        resp = _web_get(raw_url, timeout=15)
        if resp.status_code == 200:
            return resp.text[:max_chars]
    except Exception as e:
        print(f"  [GITHUB] raw.githubusercontent.com failed for {path}: {e}")

    # Fallback: scrape blob page
    blob_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"
    try:
        resp = _web_get(blob_url, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        # GitHub renders code in <table> with line numbers or in a <code> block
        code = soup.find("table", {"data-tagsearch-lang": True})
        if code:
            return code.get_text(separator="\n")[:max_chars]
        raw_div = soup.find("div", {"id": "raw-url"})
        if raw_div:
            return soup.get_text(separator="\n")[:max_chars]
    except Exception as e:
        print(f"  [GITHUB] blob page scrape failed for {path}: {e}")

    return ""


def _scrape_repo_meta(owner: str, repo: str) -> dict:
    """
    Scrape repo metadata (description, default branch, language) from GitHub web page.
    """
    url = f"https://github.com/{owner}/{repo}"
    try:
        resp = _web_get(url, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Description
        desc_tag = soup.find("p", {"class": lambda c: c and "f4" in c})
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        # Default branch — look for branch selector
        branch = "main"
        branch_btn = soup.find("span", {"class": lambda c: c and "branch" in str(c).lower()})
        if not branch_btn:
            # Try meta tags
            for link in soup.find_all("link", {"rel": "canonical"}):
                pass  # just checking page loaded
        # Try to find branch in page source
        branch_match = re.search(r'"defaultBranch":"([^"]+)"', resp.text)
        if branch_match:
            branch = branch_match.group(1)
        else:
            # Try "main" then "master"
            for b in ("main", "master", "develop"):
                test_url = f"https://github.com/{owner}/{repo}/tree/{b}"
                try:
                    tr = _web_get(test_url, timeout=8)
                    if tr.status_code == 200 and f"/tree/{b}" in tr.url:
                        branch = b
                        break
                except Exception:
                    continue

        # Language
        lang_tag = soup.find("span", {"itemprop": "programmingLanguage"})
        language = lang_tag.get_text(strip=True) if lang_tag else "Unknown"

        print(f"  [GITHUB] Scraped meta: branch={branch} lang={language} desc={description[:60]}")
        return {"description": description, "branch": branch, "language": language}

    except Exception as e:
        print(f"  [GITHUB] Meta scrape failed: {e} — using defaults")
        return {"description": "", "branch": "main", "language": "Unknown"}


def read_github_repo(repo_url: str, max_files: int = 40,
                     max_chars_per_file: int = 3000) -> dict:
    """
    Reads a GitHub repository WITHOUT using api.github.com.
    Uses github.com web pages + raw.githubusercontent.com instead,
    which works even when corporate proxies block the GitHub API.

    Strategy:
      1. Scrape github.com/{owner}/{repo} for metadata + branch
      2. Scrape file tree by walking directory pages
      3. Fetch each file from raw.githubusercontent.com
    """
    m = re.search(r"github\.com[/:]([^/\s]+)/([^/\s#?]+)", repo_url)
    if not m:
        return {"error": f"Could not parse GitHub repo URL: {repo_url}"}

    owner = m.group(1)
    repo  = m.group(2).rstrip(".git")
    print(f"  [GITHUB] Reading repo via web scrape: {owner}/{repo}")

    # ── Step 1: Repo metadata ──
    meta   = _scrape_repo_meta(owner, repo)
    branch = meta["branch"]

    # ── Step 2: File tree ──
    print(f"  [GITHUB] Walking file tree (branch: {branch})...")
    all_files = _scrape_all_files(owner, repo, branch, max_files=max_files)
    print(f"  [GITHUB] Found {len(all_files)} readable files")

    if not all_files:
        # Last resort: try to at least get the README
        print("  [GITHUB] No files scraped — trying README directly")
        for readme_name in ("README.md", "readme.md", "README.rst", "README.txt"):
            content = _fetch_raw_file(owner, repo, branch, readme_name, max_chars_per_file)
            if content.strip():
                all_files = [readme_name]
                break

    # ── Step 3: Prioritise and read files ──
    def _priority(path):
        name = path.lower()
        if re.match(r"readme", name):              return 0
        if "/" not in path:                         return 1
        if name.startswith("docs/"):               return 2
        if name.endswith((".yml", ".yaml", ".toml", ".json")): return 3
        if name.startswith(("src/", "app/", "lib/")): return 4
        return 5

    all_files.sort(key=_priority)
    selected = all_files[:max_files]
    print(f"  [GITHUB] Reading {len(selected)} files from raw.githubusercontent.com...")

    files_content = []
    readme_text   = ""

    for path in selected:
        text = _fetch_raw_file(owner, repo, branch, path, max_chars_per_file)
        if text.strip():
            files_content.append({"path": path, "content": text})
            if re.match(r"readme", path.lower()):
                readme_text = text
            print(f"  [GITHUB] ✓ {path} ({len(text)} chars)")
        else:
            print(f"  [GITHUB] ✗ {path} (empty or failed)")

    if not files_content:
        return {"error": (
            f"Could not read any files from {owner}/{repo}. "
            "The repo may be private, or both github.com and raw.githubusercontent.com "
            "are blocked by your corporate network. "
            "Try setting HTTPS_PROXY in your .env file."
        )}

    return {
        "owner":       owner,
        "repo":        repo,
        "description": meta["description"],
        "language":    meta["language"],
        "stars":       0,
        "topics":      [],
        "files":       files_content,
        "readme":      readme_text,
        "error":       None,
    }


# ── AUTO PDF extractor ─────────────────────────────────────────

def _extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        import fitz
        doc  = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        if text.strip():
            print(f"  [PDF] Extracted {len(text)} chars via PyMuPDF")
            return text.strip()
        print("  [PDF] PyMuPDF returned empty — trying pdfplumber")
    except ImportError:
        print("  [PDF] PyMuPDF not installed — trying pdfplumber")
    except Exception as e:
        print(f"  [PDF] PyMuPDF failed: {e} — trying pdfplumber")

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = []
            for i, p in enumerate(pdf.pages):
                t = p.extract_text() or ""
                pages_text.append(t)
                print(f"  [PDF] pdfplumber page {i+1}: {len(t)} chars")
            result = "\n".join(pages_text).strip()
            print(f"  [PDF] Extracted {len(result)} chars via pdfplumber")
            return result
    except ImportError:
        msg = "[PDF extraction failed: run: pip install pymupdf pdfplumber]"
        print(f"  [PDF] ERROR: {msg}")
        return msg
    except Exception as e:
        msg = f"[PDF extraction failed: {e}]"
        print(f"  [PDF] ERROR: {msg}")
        return msg


# ── AUTO Image describer ───────────────────────────────────────

def _describe_image(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    if not GROQ_API_KEY:
        return "[Image description skipped: GROQ_API_KEY not set]"
    try:
        b64 = base64.b64encode(image_bytes).decode()
        r   = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                "messages": [{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": (
                        "Describe this image in full detail. Include any text, numbers, "
                        "charts, diagrams, tables or important visual information."
                    )},
                ]}],
                "max_tokens": 600,
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[Image description failed: {e}]"


# ── AUTO URL fetcher ───────────────────────────────────────────

def _fetch_url_text(url: str, max_chars: int = 2000) -> str:
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n")).strip()[:max_chars]
    except Exception as e:
        return f"[URL fetch failed: {e}]"


# ── AUTO attachment extractor ──────────────────────────────────

def _auto_extract_attachments(page_id: str) -> str:
    try:
        data = _get(f"content/{page_id}/child/attachment", {"limit": 20})
    except Exception:
        return ""

    results = data.get("results", [])
    if not results:
        print(f"  [AUTO] No attachments on page {page_id}")
        return ""

    print(f"  [AUTO] Found {len(results)} attachment(s): {[a.get('title','?') for a in results]}")
    sections = []

    for att in results:
        title   = att.get("title", "unnamed")
        mime    = att.get("metadata", {}).get("mediaType", "")
        dl_path = att.get("_links", {}).get("download", "")
        dl_url  = f"{CONFLUENCE_URL}/wiki{dl_path}" if dl_path else None

        print(f"  [AUTO] Processing: '{title}' | mime: {mime}")
        if not dl_url:
            continue

        try:
            raw = requests.get(dl_url, auth=AUTH, timeout=30).content
            print(f"  [AUTO] Downloaded '{title}': {len(raw)} bytes")
        except Exception as e:
            sections.append(f"[Attachment '{title}': download failed — {e}]")
            print(f"  [AUTO] Download FAILED for '{title}': {e}")
            continue

        if "pdf" in mime or title.lower().endswith(".pdf"):
            text = _extract_pdf_text(raw)
            sections.append(f"[PDF: {title}]\n{text[:6000]}")
            print(f"  [AUTO] PDF '{title}' → context ({len(text)} chars)")

        elif mime.startswith("image/") or any(
            title.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")
        ):
            ext_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                       "png": "image/png",  "gif":  "image/gif", "webp": "image/webp"}
            ext     = title.rsplit(".", 1)[-1].lower() if "." in title else ""
            caption = _describe_image(raw, ext_map.get(ext, mime or "image/jpeg"))
            sections.append(f"[Image: {title}]\n{caption}")
            print(f"  [AUTO] Image '{title}' described ({len(caption)} chars)")

        else:
            sections.append(f"[Attachment: {title} — type: {mime}]")

    return "\n\n".join(sections)


# ── AUTO hyperlink extractor ───────────────────────────────────

def _auto_extract_urls(html_body: str, page_url: str) -> str:
    """
    Extracts and fetches content from ALL links inside a Confluence page:
      1. <ac:link><ri:page ri:content-title="..."/> -- internal Confluence page links (storage format)
      2. <ac:link><ri:page ri:content-id="..."/>    -- internal links by page ID
      3. <a href="...">                              -- regular hyperlinks (external or Confluence URL)
    """
    soup     = BeautifulSoup(html_body, "html.parser")
    sections = []
    seen     = set()

    # ── 1. Confluence native <ac:link> macros ──────────────────────────────
    # Confluence stores internal links as:
    #   <ac:link><ri:page ri:content-title="Page Title" ri:space-key="KEY"/></ac:link>
    for ac_link in soup.find_all("ac:link"):
        ri_page = ac_link.find("ri:page")
        if not ri_page:
            continue

        linked_title = ri_page.get("ri:content-title", "").strip()
        linked_id    = ri_page.get("ri:content-id", "").strip()

        if linked_title and linked_title not in seen:
            seen.add(linked_title)
            print(f"  [LINKS] Internal link by title: '{linked_title}'")
            inner = get_page_by_title(linked_title)
            if inner:
                inner_id   = inner["id"]
                inner_html = inner.get("body", {}).get("storage", {}).get("value", "")
                inner_text = re.sub(r"\n{3,}", "\n\n",
                    BeautifulSoup(inner_html, "html.parser").get_text(separator="\n", strip=True))
                inner_url  = f"{CONFLUENCE_URL}/wiki/spaces/{SPACE_KEY}/pages/{inner_id}"
                att_text   = _auto_extract_attachments(inner_id)
                content    = inner_text[:3000] + (f"\n\n{att_text[:2000]}" if att_text else "")
                sections.append(
                    f"[Linked Confluence Page: {inner.get('title', linked_title)}]\n"
                    f"URL: {inner_url}\n{content}"
                )
                save_url(inner_url, inner.get("title", linked_title), "confluence", SPACE_KEY)
            else:
                print(f"  [LINKS] Could not fetch linked page: '{linked_title}'")

        elif linked_id and linked_id not in seen:
            seen.add(linked_id)
            print(f"  [LINKS] Internal link by ID: {linked_id}")
            inner = get_page_by_id(linked_id)
            if inner:
                inner_html = inner.get("body", {}).get("storage", {}).get("value", "")
                inner_text = re.sub(r"\n{3,}", "\n\n",
                    BeautifulSoup(inner_html, "html.parser").get_text(separator="\n", strip=True))
                inner_url  = f"{CONFLUENCE_URL}/wiki/spaces/{SPACE_KEY}/pages/{linked_id}"
                att_text   = _auto_extract_attachments(linked_id)
                content    = inner_text[:3000] + (f"\n\n{att_text[:2000]}" if att_text else "")
                sections.append(
                    f"[Linked Confluence Page: {inner.get('title', linked_id)}]\n"
                    f"URL: {inner_url}\n{content}"
                )
                save_url(inner_url, inner.get("title", linked_id), "confluence", SPACE_KEY)

    # ── 2. Standard <a href> links ─────────────────────────────────────────
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith(("#", "mailto:")):
            continue
        if href.startswith("/"):
            href = f"{CONFLUENCE_URL}{href}"
        if not href.startswith("http"):
            continue
        if href in seen or href == page_url:
            continue
        seen.add(href)

        if CONFLUENCE_URL in href and "/pages/" in href:
            m = re.search(r"/pages/(\d+)", href)
            if m:
                inner = get_page_by_id(m.group(1))
                if inner:
                    inner_html = inner.get("body", {}).get("storage", {}).get("value", "")
                    inner_text = re.sub(r"\n{3,}", "\n\n",
                        BeautifulSoup(inner_html, "html.parser").get_text(separator="\n", strip=True))
                    att_text   = _auto_extract_attachments(inner["id"])
                    content    = inner_text[:3000] + (f"\n\n{att_text[:2000]}" if att_text else "")
                    sections.append(
                        f"[Linked Confluence Page: {inner.get('title', href)}]\n"
                        f"URL: {href}\n{content}"
                    )
                    save_url(href, inner.get("title", href), "confluence", SPACE_KEY)
                    print(f"  [LINKS] Internal page via href: '{inner.get('title', href)}'")
                    continue

        print(f"  [LINKS] External URL: {href[:80]}")
        content = _fetch_url_text(href, max_chars=1500)
        sections.append(f"[Linked URL: {href}]\n{content}")
        save_url(href, href, "external")

    print(f"  [LINKS] Linked sections fetched: {len(sections)}")
    return "\n\n".join(sections)


# ── Main context builder ───────────────────────────────────────

def build_page_context(page: dict, follow_links: bool = True) -> str:
    page_id   = page["id"]
    title     = page["title"]
    html_body = page.get("body", {}).get("storage", {}).get("value", "")
    page_url  = f"{CONFLUENCE_URL}/wiki/spaces/{SPACE_KEY}/pages/{page_id}"

    save_url(page_url, title, "confluence", SPACE_KEY)

    soup      = BeautifulSoup(html_body, "html.parser")
    body_text = re.sub(r"\n{3,}", "\n\n",
                       soup.get_text(separator="\n", strip=True))

    sections = [
        f"=== PAGE: {title} ===",
        f"URL: {page_url}",
        "",
        "--- Page Content ---",
        body_text,
    ]

    print(f"  [AUTO] Extracting attachments from '{title}'...")
    att_text = _auto_extract_attachments(page_id)
    sections += (["", "--- Attachments ---", att_text]
                 if att_text else ["", "--- Attachments: none ---"])

    url_text = ""
    if follow_links:
        print(f"  [AUTO] Fetching linked URLs from '{title}'...")
        url_text = _auto_extract_urls(html_body, page_url)
        sections += (["", "--- Linked Content ---", url_text]
                     if url_text else ["", "--- Linked URLs: none ---"])

    full = "\n".join(sections)
    print(f"  [AUTO] Context ready: {len(full)} chars | body:{len(body_text)} att:{len(att_text)} links:{len(url_text)}")
    return full


# ── Public API ─────────────────────────────────────────────────

def fetch_context_for_query(user_query: str) -> str:
    results = search_pages(user_query, limit=3)
    if results:
        page = results[0]
        if not page.get("body", {}).get("storage", {}).get("value"):
            page = get_page_by_id(page["id"])
        if page:
            return build_page_context(page, follow_links=True)

    all_pages = list_space_pages()
    if not all_pages:
        return "No pages found in the Confluence space."
    page_list = "\n".join(f"- {p['title']} (id: {p['id']})" for p in all_pages)
    return f"Available pages in space:\n{page_list}\n\nNo direct match for: {user_query}"


def fetch_context_for_page_title(title: str) -> str:
    page = get_page_by_title(title)
    if not page:
        return f"Page '{title}' not found in space {SPACE_KEY}."
    return build_page_context(page, follow_links=True)