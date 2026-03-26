import sys

sys.path.append("backend")

from pageindex.utils import get_page_tokens, get_number_of_pages

pdf_path = "backend/uploads/c171eb57-db86-4a2b-8c94-b3203fd474cc_25中级会计-实务官方教材电子书.pdf"

print(f"Extracting content from: {pdf_path}")
print(f"Total pages: {get_number_of_pages(pdf_path)}")
print("-" * 80)

page_list = get_page_tokens(pdf_path, pdf_parser="auto")

print(f"Extracted {len(page_list)} pages")
print("-" * 80)

for i, (text, token_count) in enumerate(page_list, 1):
    print(f"\n=== Page {i} ({token_count} tokens) ===")
    print(text[:500])
    if len(text) > 500:
        print("... (truncated)")
