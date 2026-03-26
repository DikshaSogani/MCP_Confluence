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
#     print(f"Exported to: {export_path}\n")


# def main():
#     print("\n🧠  Confluence AI Assistant")
#     print("Powered by Groq · LLaMA 3.3 70B")
#     print("Commands: 'history' | 'clear' | 'export' | 'exit'\n")

#     chat_history = []

#     while True:
#         try:
#             user_input = input("You: ").strip()
#         except (KeyboardInterrupt, EOFError):
#             print("\nGoodbye! History saved to history.db")
#             break

#         if not user_input:
#             continue
#         if user_input.lower() == "exit":
#             print("Goodbye! History saved to history.db")
#             break
#         if user_input.lower() == "history":
#             print_history()
#             continue
#         if user_input.lower() == "clear":
#             clear_history()
#             print("History cleared.\n")
#             continue
#         if user_input.lower() == "export":
#             export_history()
#             continue

#         print("\nFetching from Confluence...\n")

#         try:
#             result = ask(user_input, chat_history)
#             if result:
#                 answer, context, metadata = result

#                 # DEBUG — remove these two lines once metadata shows correctly
#                 print(f"[DEBUG metadata]: {metadata}")
#                 print(f"[DEBUG context start]: {context[:300]}")

#                 print(f"Assistant: {answer}")
#                 print(format_source_block(metadata))
#                 print()
#                 chat_history.append({"role": "user",      "content": user_input})
#                 chat_history.append({"role": "assistant", "content": answer})
#             else:
#                 print("Assistant: Something went wrong, please try again.\n")
#         except Exception as e:
#             import traceback
#             traceback.print_exc()


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


def main():
    print("\n🧠  Confluence AI Assistant")
    print("Powered by Groq · LLaMA 3.3 70B")
    print("─────────────────────────────────────────────────────")
    print("  Ask anything  │  or try:")
    print("  • 'Add X to the HR Policy page'")
    print("  • 'Create a new page about onboarding'")
    print("  • 'Create a wiki from https://github.com/owner/repo'")
    print("─────────────────────────────────────────────────────")
    print("  Commands: history | clear | export | exit\n")

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
    