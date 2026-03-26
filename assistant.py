
# import os
# import sys
# import pathlib
# import json
# import re

# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from groq import Groq
# from dotenv import load_dotenv
# from mcp_server import (
#     fetch_context_for_query,
#     fetch_context_for_page_title,
#     list_space_pages,
# )

# load_dotenv()

# client = Groq(api_key=os.getenv("GROQ_API_KEY"))
# MODEL  = "llama-3.3-70b-versatile"


# def _load_rules() -> tuple:
#     """
#     Reads rules.md and extracts:
#       ## [ROUTER]    -> router system prompt
#       ## [ASSISTANT] -> answer system prompt
#     Edit rules.md to change behaviour — no Python changes needed.
#     """
#     rules_path = pathlib.Path(__file__).parent / "rules.md"

#     if not rules_path.exists():
#         print("  [RULES] rules.md not found — using built-in defaults")
#         return (
#             'You are a page router. Return JSON only: {"page_title": "best match or null", "confidence": "high/medium/low"}',
#             "You are a Confluence assistant. Answer only from the provided context."
#         )

#     content = rules_path.read_text(encoding="utf-8")
#     print(f"  [RULES] Loaded rules.md ({len(content)} chars)")

#     router_match    = re.search(r"##\s*\[ROUTER\](.*?)(?=##\s*\[|$)",    content, re.DOTALL)
#     assistant_match = re.search(r"##\s*\[ASSISTANT\](.*?)(?=##\s*\[|$)", content, re.DOTALL)

#     router_prompt    = router_match.group(1).strip()    if router_match    else ""
#     assistant_prompt = assistant_match.group(1).strip() if assistant_match else ""

#     if not router_prompt:    print("  [RULES] WARNING: [ROUTER] section missing in rules.md")
#     if not assistant_prompt: print("  [RULES] WARNING: [ASSISTANT] section missing in rules.md")

#     return router_prompt, assistant_prompt


# ROUTER_PROMPT, ASSISTANT_PROMPT = _load_rules()


# def _llm_pick_page(user_query: str, page_titles: list) -> str | None:
#     """
#     LLM reads all page titles and picks the best semantic match.
#     Uses ROUTER_PROMPT loaded from rules.md ## [ROUTER] section.
#     Returns matched title or None (triggers search fallback).
#     """
#     if not page_titles:
#         return None

#     titles_list = "\n".join(f"- {t}" for t in page_titles)

#     try:
#         resp = client.chat.completions.create(
#             model=MODEL,
#             messages=[
#                 {"role": "system", "content": ROUTER_PROMPT},
#                 {"role": "user",   "content": (
#                     f"User question: {user_query}\n\n"
#                     f"Available Confluence pages:\n{titles_list}\n\n"
#                     f"Which page best answers this question? Reply with JSON only."
#                 )},
#             ],
#             max_tokens=100,
#             temperature=0.0,
#         )

#         raw = re.sub(r"```json|```", "", resp.choices[0].message.content.strip()).strip()
#         result     = json.loads(raw)
#         title      = result.get("page_title")
#         confidence = result.get("confidence", "low")

#         print(f"  [ROUTER] LLM picked: '{title}'  confidence: {confidence}")
#         return title if title and confidence in ("high", "medium") else None

#     except Exception as e:
#         print(f"  [ROUTER] Routing failed ({e}) — using search fallback")
#         return None


# def extract_metadata(context: str) -> dict:
#     """
#     Pull page title, URL, and attachment names out of the context string.
#     Returns a dict with title, url, and list of attachments.
#     """
#     metadata = {"title": None, "url": None, "attachments": []}

#     for line in context.splitlines():
#         line = line.strip()

#         if line.startswith("=== PAGE:") and line.endswith("==="):
#             metadata["title"] = line.replace("=== PAGE:", "").replace("===", "").strip()

#         elif line.startswith("URL:"):
#             metadata["url"] = line.replace("URL:", "").strip()

#         elif line.startswith("[PDF:"):
#             name = line.replace("[PDF:", "").rstrip("]").strip()
#             metadata["attachments"].append(("PDF", name))

#         elif line.startswith("[Image:"):
#             name = line.replace("[Image:", "").rstrip("]").strip()
#             metadata["attachments"].append(("Image", name))

#         elif line.startswith("[Attachment:"):
#             name = line.replace("[Attachment:", "").rstrip("]").strip()
#             metadata["attachments"].append(("File", name))

#     return metadata


# def format_source_block(metadata: dict) -> str:
#     """
#     Build a clean source info string to display below every answer.
#     """
#     lines = ["\n─────────────────────────────────────────"]
#     lines.append("  Sources used:")

#     if metadata.get("title"):
#         lines.append(f"  📄 Page    : {metadata['title']}")

#     if metadata.get("url"):
#         lines.append(f"  🔗 URL     : {metadata['url']}")

#     if metadata.get("attachments"):
#         for att_type, att_name in metadata["attachments"]:
#             icon = "📎" if att_type == "PDF" else "🖼 " if att_type == "Image" else "📁"
#             lines.append(f"  {icon} {att_type:6} : {att_name}")

#     lines.append("─────────────────────────────────────────")
#     return "\n".join(lines)


# def ask(user_query: str, chat_history: list = None):
#     """
#     1. List all pages from Confluence
#     2. LLM picks best page using [ROUTER] from rules.md
#     3. Fetch full context (auto: body + PDFs + images + URLs)
#     4. Low confidence -> CQL search fallback
#     5. Answer using [ASSISTANT] from rules.md
#     Returns: (answer, context, metadata)
#     """
#     chat_history = chat_history or []

#     try:
#         print(f"  [ROUTER] Fetching page list...")
#         all_pages   = list_space_pages()
#         page_titles = [p["title"] for p in all_pages]
#         print(f"  [ROUTER] {len(page_titles)} pages: {page_titles}")

#         matched_title = _llm_pick_page(user_query, page_titles)
#         print(f"  [DEBUG] Matched page: {matched_title}")

#         if matched_title:
#             context = fetch_context_for_page_title(matched_title)
#         else:
#             print(f"  [DEBUG] Search fallback for: {user_query}")
#             context = fetch_context_for_query(user_query)

#         print(f"  [DEBUG] Context length: {len(context)} chars")
#         print(f"  [DEBUG] Context preview: {context[:200]}")

#         messages = [{"role": "system", "content": ASSISTANT_PROMPT}]
#         for turn in chat_history[-6:]:
#             messages.append(turn)
#         messages.append({
#             "role": "user",
#             "content": (
#                 f"Here is the content fetched from Confluence:\n\n"
#                 f"{context}\n\n"
#                 f"---\n"
#                 f"Based on the above content, please answer: {user_query}"
#             ),
#         })

#         print(f"  [DEBUG] Calling Groq ({MODEL})...")
#         response = client.chat.completions.create(
#             model=MODEL,
#             messages=messages,
#             max_tokens=1024,
#             temperature=0.1,
#         )
#         answer = response.choices[0].message.content.strip()
#         print(f"  [DEBUG] Answer ready ({len(answer)} chars)")

#         metadata = extract_metadata(context)
#         return answer, context, metadata

#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return f"Error: {e}", "", {}

import os
import sys
import pathlib
import json
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groq import Groq
from dotenv import load_dotenv
from mcp_server import (
    fetch_context_for_query,
    fetch_context_for_page_title,
    list_space_pages,
    get_page_by_title,
    create_page,
    update_page,
    read_github_repo,
)

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL  = "llama-3.3-70b-versatile"


# ── Load rules.md ──────────────────────────────────────────────

def _load_rules() -> tuple:
    rules_path = pathlib.Path(__file__).parent / "rules.md"
    if not rules_path.exists():
        print("  [RULES] rules.md not found — using built-in defaults")
        return (
            'Return JSON only: {"page_title": "best match or null", "confidence": "high/medium/low"}',
            "You are a Confluence assistant. Answer only from the provided context.",
        )

    content = rules_path.read_text(encoding="utf-8")
    print(f"  [RULES] Loaded rules.md ({len(content)} chars)")

    router_match    = re.search(r"##\s*\[ROUTER\](.*?)(?=##\s*\[|$)",    content, re.DOTALL)
    assistant_match = re.search(r"##\s*\[ASSISTANT\](.*?)(?=##\s*\[|$)", content, re.DOTALL)

    router_prompt    = router_match.group(1).strip()    if router_match    else ""
    assistant_prompt = assistant_match.group(1).strip() if assistant_match else ""

    if not router_prompt:    print("  [RULES] WARNING: [ROUTER] section missing in rules.md")
    if not assistant_prompt: print("  [RULES] WARNING: [ASSISTANT] section missing in rules.md")

    return router_prompt, assistant_prompt


ROUTER_PROMPT, ASSISTANT_PROMPT = _load_rules()


# ── Intent detection ───────────────────────────────────────────

_INTENT_SYSTEM = """You are an intent classifier for a Confluence AI assistant.
Classify the user message into exactly one of these intents:

- "read"         : user wants to search/read/ask about existing Confluence pages
- "write"        : user wants to update/edit/add content to an EXISTING Confluence page
- "create"       : user wants to create a brand NEW Confluence page (plain text or content they provide)
- "github_wiki"  : user wants to create a Confluence page/wiki FROM a GitHub repository URL

Return ONLY valid JSON — no explanation, no markdown:
{
  "intent": "read|write|create|github_wiki",
  "page_title": "exact existing page title if intent is read or write, else null",
  "new_page_title": "desired title for new page if intent is create or github_wiki, else null",
  "github_url": "full github repo URL if intent is github_wiki, else null",
  "write_instruction": "what the user wants written/added if intent is write or create, else null"
}"""

def _detect_intent(user_query: str, page_titles: list) -> dict:
    titles_str = "\n".join(f"- {t}" for t in page_titles)
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM},
                {"role": "user",   "content": (
                    f"Available Confluence pages:\n{titles_str}\n\n"
                    f"User message: {user_query}"
                )},
            ],
            max_tokens=200,
            temperature=0.0,
        )
        raw    = re.sub(r"```json|```", "", resp.choices[0].message.content.strip()).strip()
        result = json.loads(raw)
        print(f"  [INTENT] {result}")
        return result
    except Exception as e:
        print(f"  [INTENT] Detection failed ({e}) — defaulting to read")
        return {"intent": "read", "page_title": None, "new_page_title": None,
                "github_url": None, "write_instruction": None}


# ── Page router (for read intent) ─────────────────────────────

def _llm_pick_page(user_query: str, page_titles: list) -> str | None:
    if not page_titles:
        return None
    titles_list = "\n".join(f"- {t}" for t in page_titles)
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user",   "content": (
                    f"User question: {user_query}\n\n"
                    f"Available Confluence pages:\n{titles_list}\n\n"
                    f"Which page best answers this question? Reply with JSON only."
                )},
            ],
            max_tokens=100,
            temperature=0.0,
        )
        raw        = re.sub(r"```json|```", "", resp.choices[0].message.content.strip()).strip()
        result     = json.loads(raw)
        title      = result.get("page_title")
        confidence = result.get("confidence", "low")
        print(f"  [ROUTER] Picked: '{title}'  confidence: {confidence}")
        return title if title and confidence in ("high", "medium") else None
    except Exception as e:
        print(f"  [ROUTER] Routing failed ({e}) — using search fallback")
        return None


# ── Metadata helpers ───────────────────────────────────────────

def extract_metadata(context: str) -> dict:
    metadata = {"title": None, "url": None, "attachments": []}
    for line in context.splitlines():
        line = line.strip()
        if line.startswith("=== PAGE:") and line.endswith("==="):
            metadata["title"] = line.replace("=== PAGE:", "").replace("===", "").strip()
        elif line.startswith("URL:"):
            metadata["url"] = line.replace("URL:", "").strip()
        elif line.startswith("[PDF:"):
            metadata["attachments"].append(("PDF", line.replace("[PDF:", "").rstrip("]").strip()))
        elif line.startswith("[Image:"):
            metadata["attachments"].append(("Image", line.replace("[Image:", "").rstrip("]").strip()))
        elif line.startswith("[Attachment:"):
            metadata["attachments"].append(("File", line.replace("[Attachment:", "").rstrip("]").strip()))
    return metadata


def format_source_block(metadata: dict) -> str:
    lines = ["\n─────────────────────────────────────────", "  Sources used:"]
    if metadata.get("title"):
        lines.append(f"  📄 Page    : {metadata['title']}")
    if metadata.get("url"):
        lines.append(f"  🔗 URL     : {metadata['url']}")
    for att_type, att_name in metadata.get("attachments", []):
        icon = "📎" if att_type == "PDF" else "🖼 " if att_type == "Image" else "📁"
        lines.append(f"  {icon} {att_type:6} : {att_name}")
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


# ── LLM: generate Confluence storage HTML ─────────────────────

def _generate_confluence_html(system_prompt: str, user_prompt: str, max_tokens: int = 2048) -> str:
    """Call Groq and return the response text (expected to be Confluence HTML)."""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


# ── WRITE: update existing page ────────────────────────────────

def _handle_write(intent: dict, user_query: str) -> tuple:
    """
    Finds the target page, generates new HTML content, and updates it.
    Returns (answer, context, metadata)
    """
    page_title = intent.get("page_title")
    instruction = intent.get("write_instruction") or user_query

    if not page_title:
        return ("I could not identify which Confluence page you want to update. "
                "Please mention the page title clearly, e.g. 'Add X to the HR Policy Guide'.",
                "", {})

    page = get_page_by_title(page_title)
    if not page:
        return (f"Could not find a Confluence page named '{page_title}'.", "", {})

    page_id      = page["id"]
    current_html = page.get("body", {}).get("storage", {}).get("value", "")

    print(f"  [WRITE] Updating page: '{page_title}' (id: {page_id})")

    system = """You are a Confluence page editor. You will receive the current page HTML 
and an instruction describing what to add or change.
Return ONLY the complete updated Confluence storage-format HTML — no explanation, no markdown fences.
Keep existing content intact unless explicitly told to replace it.
Use proper Confluence HTML: <h1>, <h2>, <p>, <ul>, <li>, <strong>, <em>, <br/>.
For code blocks use: <ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[...]]></ac:plain-text-body></ac:structured-macro>"""

    user = (
        f"Current page HTML:\n{current_html}\n\n"
        f"Instruction: {instruction}\n\n"
        f"Return the complete updated HTML only."
    )

    new_html = _generate_confluence_html(system, user, max_tokens=3000)

    result = update_page(page_id, page_title, new_html)

    if result["success"]:
        answer = (
            f"✅ Page **'{page_title}'** has been updated successfully.\n"
            f"🔗 View it here: {result['url']}"
        )
        metadata = {"title": page_title, "url": result["url"], "attachments": []}
    else:
        answer = f"❌ Failed to update page '{page_title}': {result['error']}"
        metadata = {}

    return answer, "", metadata


# ── CREATE: new page from plain instruction ────────────────────

def _handle_create(intent: dict, user_query: str) -> tuple:
    """
    Generates HTML content from the user's instruction and creates a new page.
    Returns (answer, context, metadata)
    """
    new_title   = intent.get("new_page_title") or "New Page"
    instruction = intent.get("write_instruction") or user_query

    print(f"  [CREATE] Creating new page: '{new_title}'")

    system = """You are a Confluence page creator.
Generate a well-structured, comprehensive Confluence storage-format HTML page.
Return ONLY the HTML body — no explanation, no markdown fences, no <html>/<body> tags.
Use proper Confluence HTML: <h1>, <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>.
For code blocks use: <ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[...]]></ac:plain-text-body></ac:structured-macro>

Rules:
- If the instruction is short or vague (e.g. "details about phone"), expand it into a full, useful page covering all relevant aspects of the topic
- If the instruction contains specific text to write (e.g. "hello team member good noon"), write exactly that content as the page body, nicely formatted
- Always start with a brief intro paragraph under <h1>
- Use sections (<h2>) to organise content logically
- Make the page immediately useful and complete"""

    user = (
        f"Page title: '{new_title}'\n\n"
        f"User instruction: {instruction}\n\n"
        f"Full user message for context: {user_query}\n\n"
        f"Generate the complete Confluence page HTML now."
    )

    html = _generate_confluence_html(system, user, max_tokens=2048)

    # If page with this title already exists → update it instead
    existing = get_page_by_title(new_title)
    if existing:
        print(f"  [CREATE] Page '{new_title}' already exists (id: {existing['id']}) — updating...")
        result = update_page(existing["id"], new_title, html)
        action = "updated"
    else:
        result = create_page(new_title, html)
        action = "created"

    if result["success"]:
        answer = (
            f"✅ Page **'{new_title}'** {action} successfully.\n"
            f"🔗 View it here: {result['url']}"
        )
        metadata = {"title": new_title, "url": result["url"], "attachments": []}
    else:
        answer = f"❌ Failed to {action} page '{new_title}': {result['error']}"
        metadata = {}

    return answer, "", metadata


# ── GITHUB WIKI: read repo → generate wiki page ────────────────

def _handle_github_wiki(intent: dict, user_query: str) -> tuple:
    """
    1. Reads all files from the GitHub repo
    2. LLM generates a structured Confluence wiki from the content
    3. Creates the page in Confluence
    Returns (answer, context, metadata)
    """
    github_url = intent.get("github_url")
    if not github_url:
        # Try to extract URL directly from the user query
        m = re.search(r"https?://github\.com/[^\s]+", user_query)
        github_url = m.group(0) if m else None

    if not github_url:
        return ("I could not find a GitHub URL in your message. "
                "Please include the full URL, e.g. https://github.com/owner/repo", "", {})

    # Read the repo
    print(f"  [GITHUB WIKI] Fetching repo: {github_url}")
    repo_data = read_github_repo(github_url)

    if repo_data.get("error"):
        return (f"❌ Could not read GitHub repo: {repo_data['error']}", "", {})

    owner       = repo_data["owner"]
    repo        = repo_data["repo"]
    description = repo_data.get("description", "")
    language    = repo_data.get("language", "")
    topics      = repo_data.get("topics", [])
    files       = repo_data["files"]
    readme      = repo_data.get("readme", "")

    if not files:
        return (f"❌ No readable files found in {owner}/{repo}.", "", {})

    # Build structured file summary for the LLM
    file_dump = ""
    for f in files:
        file_dump += f"\n\n=== {f['path']} ===\n{f['content']}"

    new_title = intent.get("new_page_title") or f"{owner}/{repo} — Wiki"

    print(f"  [GITHUB WIKI] Generating wiki page: '{new_title}' from {len(files)} files...")

    system = """You are a technical documentation expert creating a Confluence wiki page from a GitHub repository.
Your job is to produce a concise, factual, and well-structured wiki that developers would actually use.

Return ONLY Confluence storage-format HTML — no explanation, no markdown, no code fences around the whole output.
Use: <h1>, <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>, <br/>
For inline code use: <code>text</code>
For code blocks use: <ac:structured-macro ac:name="code"><ac:parameter ac:name="language">python</ac:parameter><ac:plain-text-body><![CDATA[code here]]></ac:plain-text-body></ac:structured-macro>

Structure your wiki with these sections (include only sections that have real content):
1. Overview — what the project does, its purpose, key tech stack
2. Architecture / How It Works — components, data flow, key design decisions
3. Setup & Installation — prerequisites, install steps, environment variables
4. Configuration — config files, important settings, .env variables
5. Usage — how to run, key commands, API endpoints or CLI usage
6. Key Files & Structure — important files/dirs and what they do
7. Dependencies — main libraries and why they are used
8. Contributing / Development Notes — how to add features, run tests

Be factual — only include information actually present in the files. Do not invent features."""

    user = (
        f"GitHub Repository: https://github.com/{owner}/{repo}\n"
        f"Description: {description}\n"
        f"Primary Language: {language}\n"
        f"Topics: {', '.join(topics) if topics else 'none'}\n\n"
        f"README:\n{readme[:3000]}\n\n"
        f"Repository Files:\n{file_dump[:12000]}\n\n"
        f"Generate the Confluence wiki page titled '{new_title}'."
    )

    html = _generate_confluence_html(system, user, max_tokens=3000)

    # If page with this title already exists → update it instead of creating
    existing = get_page_by_title(new_title)
    if existing:
        print(f"  [GITHUB WIKI] Page '{new_title}' already exists (id: {existing['id']}) — updating...")
        result = update_page(existing["id"], new_title, html)
        action = "updated"
    else:
        result = create_page(new_title, html)
        action = "created"

    if result["success"]:
        answer = (
            f"✅ Wiki page **'{new_title}'** {action} from https://github.com/{owner}/{repo}\n"
            f"📄 {len(files)} files read · {language} project\n"
            f"🔗 View it here: {result['url']}"
        )
        metadata = {"title": new_title, "url": result["url"], "attachments": []}
    else:
        answer = f"❌ Failed to {action} wiki page: {result['error']}"
        metadata = {}

    return answer, "", metadata


# ── Main ask() entry point ─────────────────────────────────────

def _extract_confluence_page_id(query: str) -> str | None:
    """
    If the user pastes a Confluence page URL like:
      https://xxx.atlassian.net/wiki/spaces/AKB/pages/6389762
    extract and return the page ID directly.
    """
    m = re.search(r"/pages/(\d+)", query)
    return m.group(1) if m else None


def ask(user_query: str, chat_history: list = None) -> tuple:
    """
    Routes every user message to the right handler:
      read         → fetch Confluence context + answer with LLM
      write        → update existing page content
      create       → create new page from instruction
      github_wiki  → read GitHub repo + create wiki page
    Returns: (answer, context, metadata)
    """
    chat_history = chat_history or []

    try:
        # ── Fast path: user pasted a Confluence page URL directly ──────────
        confluence_page_id = _extract_confluence_page_id(user_query)
        if confluence_page_id:
            print(f"  [URL DETECT] Confluence page ID found in query: {confluence_page_id}")
            from mcp_server import get_page_by_id, build_page_context
            page = get_page_by_id(confluence_page_id)
            if page:
                context = build_page_context(page, follow_links=True)
                print(f"  [URL DETECT] Fetched page '{page['title']}' directly from URL")

                messages = [{"role": "system", "content": ASSISTANT_PROMPT}]
                for turn in chat_history[-6:]:
                    messages.append(turn)
                messages.append({
                    "role": "user",
                    "content": (
                        f"Here is the content fetched from Confluence:\n\n"
                        f"{context}\n\n---\n"
                        f"Based on the above content, please answer: {user_query}"
                    ),
                })
                response = client.chat.completions.create(
                    model=MODEL, messages=messages, max_tokens=1024, temperature=0.1,
                )
                answer   = response.choices[0].message.content.strip()
                metadata = extract_metadata(context)
                return answer, context, metadata

        print(f"  [ROUTER] Fetching page list...")
        all_pages   = list_space_pages()
        page_titles = [p["title"] for p in all_pages]
        print(f"  [ROUTER] {len(page_titles)} pages: {page_titles}")

        intent = _detect_intent(user_query, page_titles)
        mode   = intent.get("intent", "read")

        # ── Write / Create / GitHub routes ──
        if mode == "write":
            return _handle_write(intent, user_query)

        if mode == "create":
            return _handle_create(intent, user_query)

        if mode == "github_wiki":
            return _handle_github_wiki(intent, user_query)

        # ── Default: Read ──
        matched_title = intent.get("page_title") or _llm_pick_page(user_query, page_titles)
        print(f"  [DEBUG] Matched page: {matched_title}")

        if matched_title:
            context = fetch_context_for_page_title(matched_title)
        else:
            print(f"  [DEBUG] Search fallback for: {user_query}")
            context = fetch_context_for_query(user_query)

        print(f"  [DEBUG] Context: {len(context)} chars")

        messages = [{"role": "system", "content": ASSISTANT_PROMPT}]
        for turn in chat_history[-6:]:
            messages.append(turn)
        messages.append({
            "role": "user",
            "content": (
                f"Here is the content fetched from Confluence:\n\n"
                f"{context}\n\n---\n"
                f"Based on the above content, please answer: {user_query}"
            ),
        })

        print(f"  [DEBUG] Calling Groq ({MODEL})...")
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.1,
        )
        answer = response.choices[0].message.content.strip()
        print(f"  [DEBUG] Answer ready ({len(answer)} chars)")

        metadata = extract_metadata(context)
        return answer, context, metadata

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error: {e}", "", {}