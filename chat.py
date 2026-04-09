
# import sys
# import os
# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# from assistant import ask, format_source_block
# from history_store import get_history, clear_history


# def print_history():
#     history = get_history(limit=50)
#     if not history:
#         print("\n  (no history yet)\n")
#         return
#     print("\n─────────────────────────────────────────────────────")
#     print(f"  URL History ({len(history)} items)")
#     print("─────────────────────────────────────────────────────")
#     for i, item in enumerate(history, 1):
#         icon     = "[page]" if item["page_type"] == "confluence" else "[link]"
#         title    = item["title"][:55] if item["title"] else item["url"][:55]
#         accessed = item["accessed_at"][:16].replace("T", " ")
#         print(f"  {i:2}. {icon} {title}")
#         print(f"       {accessed}  |  {item['url'][:70]}")
#     print("─────────────────────────────────────────────────────\n")


# def export_history():
#     history     = get_history(limit=200)
#     export_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history_export.txt")
#     with open(export_path, "w", encoding="utf-8") as f:
#         f.write("Confluence AI Assistant — History Export\n")
#         f.write("=" * 50 + "\n\n")
#         for item in history:
#             f.write(f"[{item['accessed_at'][:16]}] {item['page_type'].upper()}\n")
#             f.write(f"  Title : {item['title']}\n")
#             f.write(f"  URL   : {item['url']}\n\n")
#     print(f"  Exported to: {export_path}\n")


# def main():
#     print("\n🧠  Confluence AI Assistant")
#     print("Powered by Groq · LLaMA 3.3 70B")
#     print("─────────────────────────────────────────────────────")
#     print("  Ask anything  │  or try:")
#     print("  • 'Add X to the HR Policy page'")
#     print("  • 'Create a new page about onboarding'")
#     print("  • 'Create a wiki from https://github.com/owner/repo'")
#     print("─────────────────────────────────────────────────────")
#     print("  Commands: history | clear | export | exit\n")

#     chat_history = []

#     while True:
#         try:
#             user_input = input("You: ").strip()
#         except (KeyboardInterrupt, EOFError):
#             print("\nGoodbye!")
#             break

#         if not user_input:
#             continue

#         # ── Guard: ignore lines that look like debug/terminal output ──────
#         # This prevents accidental paste of terminal logs being treated as queries
#         _debug_prefixes = (
#             "[router]", "[intent]", "[debug]", "[auto]", "[write]",
#             "[create]", "[github]", "[links]", "[rules]", "[pdf]",
#             "[url detect]", "[github wiki]",
#             "thinking...", "assistant:", "you:",
#             "fetching from confluence", "─────",
#         )
#         if any(user_input.lower().startswith(p) for p in _debug_prefixes):
#             print("  [!] That looks like debug/terminal output -- please type your question.\n")
#             continue

#         if user_input.lower() == "exit":
#             print("Goodbye!")
#             break
#         if user_input.lower() == "history":
#             print_history()
#             continue
#         if user_input.lower() == "clear":
#             clear_history()
#             print("  History cleared.\n")
#             continue
#         if user_input.lower() == "export":
#             export_history()
#             continue

#         print("\nThinking...\n")

#         try:
#             result = ask(user_input, chat_history)
#             if not result:
#                 print("Assistant: Something went wrong, please try again.\n")
#                 continue

#             answer, context, metadata = result

#             print(f"Assistant: {answer}\n")

#             # Only show source block for read operations that have real metadata
#             if metadata.get("title") or metadata.get("url"):
#                 print(format_source_block(metadata))

#             print()
#             chat_history.append({"role": "user",      "content": user_input})
#             chat_history.append({"role": "assistant",  "content": answer})

#         except Exception as e:
#             import traceback
#             traceback.print_exc()
#             print(f"Assistant: Sorry, an error occurred: {e}\n")


# if __name__ == "__main__":
#     main()


import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from assistant import ask, format_source_block
from history_store import get_history, clear_history


def print_history():
    history = get_history(limit=50)
    if not history:
        print("\n  (no history yet)\n")
        return
    print("\n─────────────────────────────────────────────────────")
    print(f"  URL History ({len(history)} items)")
    print("─────────────────────────────────────────────────────")
    for i, item in enumerate(history, 1):
        icon     = "[page]" if item["page_type"] == "confluence" else "[link]"
        title    = item["title"][:55] if item["title"] else item["url"][:55]
        accessed = item["accessed_at"][:16].replace("T", " ")
        print(f"  {i:2}. {icon} {title}")
        print(f"       {accessed}  |  {item['url'][:70]}")
    print("─────────────────────────────────────────────────────\n")


def export_history():
    history     = get_history(limit=200)
    export_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history_export.txt")
    with open(export_path, "w", encoding="utf-8") as f:
        f.write("Confluence AI Assistant — History Export\n")
        f.write("=" * 50 + "\n\n")
        for item in history:
            f.write(f"[{item['accessed_at'][:16]}] {item['page_type'].upper()}\n")
            f.write(f"  Title : {item['title']}\n")
            f.write(f"  URL   : {item['url']}\n\n")
    print(f"  Exported to: {export_path}\n")


def sync_to_qdrant():
    """Fetch all Confluence pages and index them in Qdrant."""
    try:
        import vector_store as vs
        from mcp_server import list_space_pages, build_page_context, get_page_by_id
    except ImportError as e:
        print(f"  [SYNC] Cannot sync: {e}")
        print("  Run: pip install qdrant-client sentence-transformers")
        return

    print("\n  [SYNC] Starting full Confluence sync to Qdrant...")
    pages = list_space_pages()
    if not pages:
        print("  [SYNC] No pages found. Check your .env credentials.")
        return

    print(f"  [SYNC] Indexing {len(pages)} pages...")
    total_chunks = 0
    for i, page_meta in enumerate(pages, 1):
        try:
            page = get_page_by_id(page_meta["id"])
            if not page:
                continue
            from mcp_server import CONFLUENCE_URL, SPACE_KEY
            url = f"{CONFLUENCE_URL}/wiki/spaces/{SPACE_KEY}/pages/{page['id']}"
            context = build_page_context(page, follow_links=False)
            n = vs.index_page_from_context(page["id"], page["title"], url, context)
            total_chunks += n
            print(f"  [SYNC] ({i}/{len(pages)}) '{page['title']}' — {n} chunks")
        except Exception as e:
            print(f"  [SYNC] Failed to index '{page_meta['title']}': {e}")

    stats = vs.get_stats()
    print(f"\n  [SYNC] Done. {total_chunks} chunks indexed across {stats.get('total_pages',0)} pages.\n")


def print_vstats():
    """Show Qdrant collection statistics."""
    try:
        import vector_store as vs
        stats = vs.get_stats()
        if "error" in stats:
            print(f"\n  [VECTOR] Error: {stats['error']}\n")
            return
        print("\n─────────────────────────────────────────────────────")
        print(f"  Qdrant Stats: {stats['total_chunks']} chunks | {stats['total_pages']} pages")
        print("─────────────────────────────────────────────────────")
        for pid, title in stats.get("pages", {}).items():
            print(f"    {title}")
        print("─────────────────────────────────────────────────────\n")
    except ImportError:
        print("  [VECTOR] qdrant-client not installed. Run: pip install qdrant-client sentence-transformers\n")


def main():
    print("\n🧠  Confluence AI Assistant")
    print("Powered by Groq · LLaMA 3.3 70B")
    print("─────────────────────────────────────────────────────")
    print("  Ask anything  │  or try:")
    print("  • 'Add X to the HR Policy page'")
    print("  • 'Create a new page about onboarding'")
    print("  • 'Create a wiki from https://github.com/owner/repo'")
    print("─────────────────────────────────────────────────────")
    print("  Commands: history | clear | export | sync | vstats | exit\n")

    chat_history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # ── Guard: ignore lines that look like debug/terminal output ──────
        # This prevents accidental paste of terminal logs being treated as queries
        _debug_prefixes = (
            "[router]", "[intent]", "[debug]", "[auto]", "[write]",
            "[create]", "[github]", "[links]", "[rules]", "[pdf]",
            "[url detect]", "[github wiki]",
            "thinking...", "assistant:", "you:",
            "fetching from confluence", "─────",
        )
        if any(user_input.lower().startswith(p) for p in _debug_prefixes):
            print("  [!] That looks like debug/terminal output -- please type your question.\n")
            continue

        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        if user_input.lower() == "history":
            print_history()
            continue
        if user_input.lower() == "clear":
            clear_history()
            print("  History cleared.\n")
            continue
        if user_input.lower() == "export":
            export_history()
            continue
        if user_input.lower() == "sync":
            sync_to_qdrant()
            continue
        if user_input.lower() == "vstats":
            print_vstats()
            continue

        print("\nThinking...\n")

        try:
            result = ask(user_input, chat_history)
            if not result:
                print("Assistant: Something went wrong, please try again.\n")
                continue

            answer, context, metadata = result

            print(f"Assistant: {answer}\n")

            # Only show source block for read operations that have real metadata
            if metadata.get("title") or metadata.get("url"):
                print(format_source_block(metadata))

            print()
            chat_history.append({"role": "user",      "content": user_input})
            chat_history.append({"role": "assistant",  "content": answer})

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Assistant: Sorry, an error occurred: {e}\n")


if __name__ == "__main__":
    main()