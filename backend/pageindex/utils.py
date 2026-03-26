import tiktoken
import openai
import logging
import os
import re
import hashlib
from datetime import datetime
import time
import json
import PyPDF2
import copy
import asyncio
import pymupdf
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
import yaml
from types import SimpleNamespace as config

CHATGPT_API_KEY = os.getenv("CHATGPT_API_KEY")
CHATGPT_BASE_URL = os.getenv("CHATGPT_BASE_URL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or os.getenv("MINIMAX_API_KEY")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL") or "https://api.minimaxi.com/anthropic"

MODEL_TO_ENCODING = {
    "qwen": "cl100k_base",
    "deepseek": "cl100k_base",
    "gemini": "cl100k_base",
    "gpt": "cl100k_base",
}


def _is_anthropic_model(model: str) -> bool:
    if model is None:
        return False
    return model.startswith("MiniMax-") or "anthropic" in model.lower()


def _build_messages(prompt, chat_history=None):
    if chat_history:
        messages = list(chat_history)
        messages.append({"role": "user", "content": prompt})
    else:
        messages = [{"role": "user", "content": prompt}]
    return messages


def get_encoding_for_model(model):
    if model is None:
        return tiktoken.get_encoding("cl100k_base")
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        model_lower = model.lower()
        for prefix, encoding in MODEL_TO_ENCODING.items():
            if model_lower.startswith(prefix):
                return tiktoken.get_encoding(encoding)
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text, model=None):
    if not text:
        return 0
    enc = get_encoding_for_model(model)
    tokens = enc.encode(text)
    return len(tokens)


def get_model_for_task(task_type: str, opt=None) -> str:
    if opt is None:
        return "qwen-max"

    task_to_profile = getattr(opt, "task_to_profile", None)
    model_profiles = getattr(opt, "model_profiles", None)

    if task_to_profile is None or model_profiles is None:
        return getattr(opt, "model", "qwen-max")

    if hasattr(task_to_profile, "get"):
        profile = task_to_profile.get(task_type, "heavy")
    else:
        profile = getattr(task_to_profile, task_type, "heavy")

    if hasattr(model_profiles, "get"):
        return model_profiles.get(profile, getattr(opt, "model", "qwen-max"))
    else:
        return getattr(model_profiles, profile, getattr(opt, "model", "qwen-max"))


def get_task_params(task_type: str, opt=None) -> dict:
    default_params = {"temperature": 0}
    if opt is None:
        return default_params

    task_params = getattr(opt, "task_params", None)

    if task_params is None:
        return default_params

    if hasattr(task_params, "get"):
        return task_params.get(task_type, default_params)
    else:
        return getattr(task_params, task_type, default_params)


def ChatGPT_API_with_finish_reason(
    model,
    prompt,
    api_key=CHATGPT_API_KEY,
    base_url=CHATGPT_BASE_URL,
    chat_history=None,
    task_params=None,
):
    max_retries = 10

    if _is_anthropic_model(model):
        import anthropic
        client = anthropic.Anthropic(
            api_key=ANTHROPIC_API_KEY or api_key,
            base_url=ANTHROPIC_BASE_URL,
            timeout=anthropic.Timeout(600.0, connect=60.0),
        )
        for i in range(max_retries):
            try:
                messages = _build_messages(prompt, chat_history)
                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0,
                }
                if task_params:
                    params.update({k: v for k, v in task_params.items() if v is not None})

                params["thinking"] = {"type": "disabled"}

                response = client.messages.create(**params)

                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                total_tokens = input_tokens + output_tokens
                print(f"[LLM] {model} | IN:{input_tokens} OUT:{output_tokens} TOT:{total_tokens}")

                text_content = ""
                for block in response.content:
                    if block.type == "text":
                        text_content += block.text
                    elif block.type == "thinking":
                        pass

                if response.stop_reason == "max_tokens":
                    return text_content, "max_output_reached"
                else:
                    return text_content, "finished"

            except Exception as e:
                print(f"[RETRY] Attempt {i+1}/{max_retries} failed: {type(e).__name__}: {e}")
                if i < max_retries - 1:
                    time.sleep(1)
                else:
                    print(f"[ERROR] All {max_retries} retries exhausted for model {model}")
                    return "Error"
    else:
        import httpx
        http_client = httpx.Client(proxy=None, timeout=300.0)
        client = openai.OpenAI(
            api_key=api_key, base_url=base_url, timeout=300.0, max_retries=3, http_client=http_client
        )
        for i in range(max_retries):
            try:
                messages = _build_messages(prompt, chat_history)

                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0,
                }
                if task_params:
                    params.update({k: v for k, v in task_params.items() if v is not None})

                response = client.chat.completions.create(**params)

                usage = response.usage
                input_tokens = usage.prompt_tokens if usage else 0
                output_tokens = usage.completion_tokens if usage else 0
                total_tokens = usage.total_tokens if usage else 0

                print(
                    f"[LLM] {model} | IN:{input_tokens} OUT:{output_tokens} TOT:{total_tokens}"
                )

                if response.choices[0].finish_reason == "length":
                    return response.choices[0].message.content, "max_output_reached"
                else:
                    return response.choices[0].message.content, "finished"

            except Exception as e:
                print(f"[RETRY] Attempt {i+1}/{max_retries} failed: {type(e).__name__}: {e}")
                if i < max_retries - 1:
                    time.sleep(1)
                else:
                    print(f"[ERROR] All {max_retries} retries exhausted for model {model}")
                    return "Error"


def ChatGPT_API(
    model,
    prompt,
    api_key=CHATGPT_API_KEY,
    base_url=CHATGPT_BASE_URL,
    chat_history=None,
    task_params=None,
):
    max_retries = 10

    if _is_anthropic_model(model):
        import anthropic
        client = anthropic.Anthropic(
            api_key=ANTHROPIC_API_KEY or api_key,
            base_url=ANTHROPIC_BASE_URL,
            timeout=anthropic.Timeout(600.0, connect=60.0),
        )
        for i in range(max_retries):
            try:
                messages = _build_messages(prompt, chat_history)
                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0,
                }
                if task_params:
                    params.update({k: v for k, v in task_params.items() if v is not None})

                params["thinking"] = {"type": "disabled"}

                response = client.messages.create(**params)

                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                total_tokens = input_tokens + output_tokens
                print(f"[LLM] {model} | IN:{input_tokens} OUT:{output_tokens} TOT:{total_tokens}")

                text_content = ""
                for block in response.content:
                    if block.type == "text":
                        text_content += block.text
                    elif block.type == "thinking":
                        pass

                print(f"[DEBUG] Response content blocks: {[(b.type, getattr(b, 'text', None) or getattr(b, 'thinking', None)) for b in response.content]}")
                print(f"[DEBUG] Extracted text_content: '{text_content[:200]}...' " if len(text_content) > 200 else f"[DEBUG] Extracted text_content: '{text_content}'")

                return text_content

            except Exception as e:
                print(f"[RETRY] Attempt {i+1}/{max_retries} failed: {type(e).__name__}: {e}")
                if i < max_retries - 1:
                    time.sleep(1)
                else:
                    print(f"[ERROR] All {max_retries} retries exhausted for model {model}")
                    return "Error"
    else:
        import httpx
        http_client = httpx.Client(proxy=None, timeout=300.0)
        client = openai.OpenAI(
            api_key=api_key, base_url=base_url, timeout=300.0, max_retries=3, http_client=http_client
        )
        for i in range(max_retries):
            try:
                messages = _build_messages(prompt, chat_history)

                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0,
                }
                if task_params:
                    params.update({k: v for k, v in task_params.items() if v is not None})

                response = client.chat.completions.create(**params)

                usage = response.usage
                input_tokens = usage.prompt_tokens if usage else 0
                output_tokens = usage.completion_tokens if usage else 0
                total_tokens = usage.total_tokens if usage else 0

                print(
                    f"[LLM] {model} | IN:{input_tokens} OUT:{output_tokens} TOT:{total_tokens}"
                )

                return response.choices[0].message.content
            except Exception as e:
                print(f"[RETRY] Attempt {i+1}/{max_retries} failed: {type(e).__name__}: {e}")
                if i < max_retries - 1:
                    time.sleep(1)
                else:
                    print(f"[ERROR] All {max_retries} retries exhausted for model {model}")
                    return "Error"


_async_client = None
_async_anthropic_client = None
_async_semaphore = asyncio.Semaphore(5)


async def ChatGPT_API_async(
    model, prompt, api_key=CHATGPT_API_KEY, base_url=CHATGPT_BASE_URL, task_params=None
):
    global _async_client, _async_anthropic_client

    max_retries = 10
    messages = [{"role": "user", "content": prompt}]

    if _is_anthropic_model(model):
        if _async_anthropic_client is None:
            import anthropic
            _async_anthropic_client = anthropic.AsyncAnthropic(
                api_key=ANTHROPIC_API_KEY or api_key,
                base_url=ANTHROPIC_BASE_URL,
                timeout=anthropic.Timeout(600.0, connect=60.0),
            )
        for i in range(max_retries):
            try:
                async with _async_semaphore:
                    params = {
                        "model": model,
                        "messages": messages,
                        "temperature": 0,
                    }
                    if task_params:
                        params.update(
                            {k: v for k, v in task_params.items() if v is not None}
                        )

                    params["thinking"] = {"type": "disabled"}

                    response = await _async_anthropic_client.messages.create(**params)

                    input_tokens = response.usage.input_tokens
                    output_tokens = response.usage.output_tokens
                    total_tokens = input_tokens + output_tokens
                    print(f"[LLM] {model} | IN:{input_tokens} OUT:{output_tokens} TOT:{total_tokens}")

                    text_content = ""
                    for block in response.content:
                        if block.type == "text":
                            text_content += block.text
                        elif block.type == "thinking":
                            pass

                    return text_content
            except Exception as e:
                print("************* Retrying *************")
                logging.error(f"Error: {e}")
                if i < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    logging.error("Max retries reached for prompt: " + prompt)
                    return "Error"
    else:
        if _async_client is None:
            import httpx
            http_client = httpx.AsyncClient(proxy=None, timeout=300.0)
            _async_client = openai.AsyncOpenAI(
                api_key=api_key, base_url=base_url, timeout=300.0, max_retries=3, http_client=http_client
            )
        for i in range(max_retries):
            try:
                async with _async_semaphore:
                    params = {
                        "model": model,
                        "messages": messages,
                        "temperature": 0,
                    }
                    if task_params:
                        params.update(
                            {k: v for k, v in task_params.items() if v is not None}
                        )

                    response = await _async_client.chat.completions.create(**params)

                    usage = response.usage
                    input_tokens = usage.prompt_tokens if usage else 0
                    output_tokens = usage.completion_tokens if usage else 0
                    total_tokens = usage.total_tokens if usage else 0

                    print(
                        f"[LLM] {model} | IN:{input_tokens} OUT:{output_tokens} TOT:{total_tokens}"
                    )

                    return response.choices[0].message.content
            except Exception as e:
                print("************* Retrying *************")
                logging.error(f"Error: {e}")
                if i < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    logging.error("Max retries reached for prompt: " + prompt)
                    return "Error"


def get_json_content(response):
    start_idx = response.find("```json")
    if start_idx != -1:
        start_idx += 7
        response = response[start_idx:]

    end_idx = response.rfind("```")
    if end_idx != -1:
        response = response[:end_idx]

    json_content = response.strip()
    return json_content


def extract_json(content):
    try:
        # First, try to extract JSON enclosed within ```json and ```
        start_idx = content.find("```json")
        if start_idx != -1:
            start_idx += 7  # Adjust index to start after the delimiter
            end_idx = content.rfind("```")
            json_content = content[start_idx:end_idx].strip()
        else:
            # If no delimiters, assume entire content could be JSON
            json_content = content.strip()

        # Clean up common issues that might cause parsing errors
        json_content = json_content.replace(
            "None", "null"
        )  # Replace Python None with JSON null
        json_content = json_content.replace("\n", " ").replace(
            "\r", " "
        )  # Remove newlines
        json_content = " ".join(json_content.split())  # Normalize whitespace

        # Attempt to parse and return the JSON object
        return json.loads(json_content)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to extract JSON: {e}")
        # Try to clean up the content further if initial parsing fails
        try:
            # Remove any trailing commas before closing brackets/braces
            json_content = json_content.replace(",]", "]").replace(",}", "}")
            return json.loads(json_content)
        except:
            logging.error("Failed to parse JSON even after cleanup")
            return {}
    except Exception as e:
        logging.error(f"Unexpected error while extracting JSON: {e}")
        return {}


def write_node_id(data, node_id=0):
    if isinstance(data, dict):
        data["node_id"] = str(node_id).zfill(4)
        node_id += 1
        for key in list(data.keys()):
            if "nodes" in key:
                node_id = write_node_id(data[key], node_id)
    elif isinstance(data, list):
        for index in range(len(data)):
            node_id = write_node_id(data[index], node_id)
    return node_id


def get_nodes(structure):
    if isinstance(structure, dict):
        structure_node = copy.deepcopy(structure)
        structure_node.pop("nodes", None)
        nodes = [structure_node]
        for key in list(structure.keys()):
            if "nodes" in key:
                nodes.extend(get_nodes(structure[key]))
        return nodes
    elif isinstance(structure, list):
        nodes = []
        for item in structure:
            nodes.extend(get_nodes(item))
        return nodes


def structure_to_list(structure):
    if isinstance(structure, dict):
        nodes = []
        nodes.append(structure)
        if "nodes" in structure:
            nodes.extend(structure_to_list(structure["nodes"]))
        return nodes
    elif isinstance(structure, list):
        nodes = []
        for item in structure:
            nodes.extend(structure_to_list(item))
        return nodes


def get_leaf_nodes(structure):
    if isinstance(structure, dict):
        if not structure["nodes"]:
            structure_node = copy.deepcopy(structure)
            structure_node.pop("nodes", None)
            return [structure_node]
        else:
            leaf_nodes = []
            for key in list(structure.keys()):
                if "nodes" in key:
                    leaf_nodes.extend(get_leaf_nodes(structure[key]))
            return leaf_nodes
    elif isinstance(structure, list):
        leaf_nodes = []
        for item in structure:
            leaf_nodes.extend(get_leaf_nodes(item))
        return leaf_nodes


def is_leaf_node(data, node_id):
    # Helper function to find the node by its node_id
    def find_node(data, node_id):
        if isinstance(data, dict):
            if data.get("node_id") == node_id:
                return data
            for key in data.keys():
                if "nodes" in key:
                    result = find_node(data[key], node_id)
                    if result:
                        return result
        elif isinstance(data, list):
            for item in data:
                result = find_node(item, node_id)
                if result:
                    return result
        return None

    # Find the node with the given node_id
    node = find_node(data, node_id)

    # Check if the node is a leaf node
    if node and not node.get("nodes"):
        return True
    return False


def get_last_node(structure):
    return structure[-1]


def extract_text_from_pdf(pdf_path):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    ###return text not list
    text = ""
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text += page.extract_text()
    return text


def get_pdf_title(pdf_path):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    meta = pdf_reader.metadata
    title = meta.title if meta and meta.title else "Untitled"
    return title


def get_text_of_pages(pdf_path, start_page, end_page, tag=True):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    text = ""
    for page_num in range(start_page - 1, end_page):
        page = pdf_reader.pages[page_num]
        page_text = page.extract_text()
        if tag:
            text += f"<start_index_{page_num + 1}>\n{page_text}\n<end_index_{page_num + 1}>\n"
        else:
            text += page_text
    return text


def get_first_start_page_from_text(text):
    start_page = -1
    start_page_match = re.search(r"<start_index_(\d+)>", text)
    if start_page_match:
        start_page = int(start_page_match.group(1))
    return start_page


def get_last_start_page_from_text(text):
    start_page = -1
    # Find all matches of start_index tags
    start_page_matches = re.finditer(r"<start_index_(\d+)>", text)
    # Convert iterator to list and get the last match if any exist
    matches_list = list(start_page_matches)
    if matches_list:
        start_page = int(matches_list[-1].group(1))
    return start_page


def sanitize_filename(filename, replacement="-"):
    # In Linux, only '/' and '\0' (null) are invalid in filenames.
    # Null can't be represented in strings, so we only handle '/'.
    return filename.replace("/", replacement)


def get_pdf_name(pdf_path):
    # Extract PDF name
    if isinstance(pdf_path, str):
        pdf_name = os.path.basename(pdf_path)
    elif isinstance(pdf_path, BytesIO):
        pdf_reader = PyPDF2.PdfReader(pdf_path)
        meta = pdf_reader.metadata
        pdf_name = meta.title if meta and meta.title else "Untitled"
        pdf_name = sanitize_filename(pdf_name)
    return pdf_name


class JsonLogger:
    def __init__(self, file_path):
        # Extract PDF name for logger name
        pdf_name = get_pdf_name(file_path)

        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"{pdf_name}_{current_time}.json"
        os.makedirs("./logs", exist_ok=True)
        # Initialize empty list to store all messages
        self.log_data = []

    def log(self, level, message, **kwargs):
        if isinstance(message, dict):
            self.log_data.append(message)
        else:
            self.log_data.append({"message": message})
        # Add new message to the log data

        # Write entire log data to file
        with open(self._filepath(), "w") as f:
            json.dump(self.log_data, f, indent=2)

    def info(self, message, **kwargs):
        self.log("INFO", message, **kwargs)

    def error(self, message, **kwargs):
        self.log("ERROR", message, **kwargs)

    def debug(self, message, **kwargs):
        self.log("DEBUG", message, **kwargs)

    def exception(self, message, **kwargs):
        kwargs["exception"] = True
        self.log("ERROR", message, **kwargs)

    def _filepath(self):
        return os.path.join("logs", self.filename)


def list_to_tree(data):
    def get_parent_structure(structure):
        """Helper function to get the parent structure code"""
        if not structure:
            return None
        parts = str(structure).split(".")
        return ".".join(parts[:-1]) if len(parts) > 1 else None

    # First pass: Create nodes and track parent-child relationships
    nodes = {}
    root_nodes = []

    for item in data:
        structure = item.get("structure")
        node = {
            "title": item.get("title"),
            "start_index": item.get("start_index"),
            "end_index": item.get("end_index"),
            "nodes": [],
        }

        nodes[structure] = node

        # Find parent
        parent_structure = get_parent_structure(structure)

        if parent_structure:
            # Add as child to parent if parent exists
            if parent_structure in nodes:
                nodes[parent_structure]["nodes"].append(node)
            else:
                root_nodes.append(node)
        else:
            # No parent, this is a root node
            root_nodes.append(node)

    # Helper function to clean empty children arrays
    def clean_node(node):
        if not node["nodes"]:
            del node["nodes"]
        else:
            for child in node["nodes"]:
                clean_node(child)
        return node

    # Clean and return the tree
    return [clean_node(node) for node in root_nodes]


def add_preface_if_needed(data):
    if not isinstance(data, list) or not data:
        return data

    if data[0]["physical_index"] is not None and data[0]["physical_index"] > 1:
        preface_node = {
            "structure": "0",
            "title": "Preface",
            "physical_index": 1,
        }
        data.insert(0, preface_node)
    return data


def get_page_tokens(
    pdf_path,
    model="qwen-max",
    pdf_parser="auto",
    max_pages=None,
    use_cache=True,
    progress_callback=None,
    start_page=1,
    cached_pages=None,
):
    """Extract text from PDF pages with optional caching."""
    enc = get_encoding_for_model(model)

    # Cache settings
    cache_dir = Path("cache/page_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Get cache file path (based on PDF path hash)
    pdf_hash = hashlib.md5(str(pdf_path).encode()).hexdigest()
    cache_file = cache_dir / f"{pdf_hash}.json"

    # Check cache if enabled
    if use_cache and cached_pages is not None:
        # cached_count is the number of cached pages (length)
        # start_page is 1-based page number to start processing from
        cached_count = len(cached_pages)
        # When start_page > cached_count, all needed pages are already cached
        if start_page > cached_count:
            print(f"[Cache] All {cached_count} pages already cached")
            return cached_pages
        print(f"[Cache] Using {cached_count} cached pages, will merge with new pages from page {start_page}")

    if use_cache:
        try:
            if cache_file.exists():
                print(f"[Cache] Loading OCR cache from {cache_file}")
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)

                page_list = [
                    (page["text"], page["tokens"]) for page in cache_data["pages"]
                ]
                print(f"[Cache] ✅ Loaded {len(page_list)} pages from cache")
                return page_list
        except Exception as e:
            print(f"[Cache] Failed to load cache: {e}")

    def try_pypdf2(pdf_path, max_pages=None):
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_path)
            total_pages = len(pdf_reader.pages)
            pages_to_process = (
                total_pages if max_pages is None else min(max_pages, total_pages)
            )
            page_list = []
            for page_num in range(pages_to_process):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                token_length = len(enc.encode(page_text))
                page_list.append((page_text, token_length))
            return page_list
        except Exception as e:
            logging.warning(f"PyPDF2 extraction failed: {e}")
            return None

    def try_pymupdf(pdf_path, max_pages=None):
        try:
            if isinstance(pdf_path, BytesIO):
                doc = pymupdf.open(stream=pdf_path, filetype="pdf")
            elif (
                isinstance(pdf_path, str)
                and os.path.isfile(pdf_path)
                and pdf_path.lower().endswith(".pdf")
            ):
                doc = pymupdf.open(pdf_path)
            else:
                return None

            total_pages = len(doc)
            pages_to_process = (
                total_pages if max_pages is None else min(max_pages, total_pages)
            )
            page_list = []
            for i, page in enumerate(doc):
                if i >= pages_to_process:
                    break
                page_text = page.get_text()
                token_length = len(enc.encode(page_text))
                page_list.append((page_text, token_length))
            doc.close()
            return page_list
        except Exception as e:
            logging.warning(f"PyMuPDF extraction failed: {e}")
            return None

    def needs_ocr(page_list):
        if not page_list:
            return True
        total_text = sum(len(p[0]) for p in page_list)
        avg_text = total_text / len(page_list) if page_list else 0
        return avg_text < 100

    def try_paddleocr(pdf_path, max_pages=None):
        """Extract text from PDF using PaddleOCR (free, local OCR)"""
        try:
            from paddleocr import PaddleOCR
            import logging as paddle_logging

            try:
                paddle_logging.getLogger("ppocr").setLevel(paddle_logging.ERROR)
            except Exception:
                pass

            print(f"[PaddleOCR] Initializing OCR model...")
            ocr = PaddleOCR(use_angle_cls=True, lang="ch")

            doc = pymupdf.open(pdf_path)
            total_pages = len(doc)
            doc.close()

            print(f"[PaddleOCR] Processing {total_pages} pages...")

            page_list = []
            pages_to_process = (
                total_pages if max_pages is None else min(max_pages, total_pages)
            )

            for page_num in range(pages_to_process):
                if page_num % 10 == 0:
                    print(
                        f"[PaddleOCR] Processing page {page_num + 1}/{pages_to_process}..."
                    )

                doc = pymupdf.open(pdf_path)
                page = doc[page_num]
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                img_data = pix.tobytes("png")
                doc.close()

                import tempfile
                import os

                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(img_data)
                    tmp_path = tmp.name

                try:
                    result = ocr.ocr(tmp_path, cls=True)
                    page_text = ""
                    if result:
                        if isinstance(result, list) and len(result) > 0:
                            if result[0]:
                                text_lines = []
                                for line in result[0]:
                                    if (
                                        line
                                        and isinstance(line, list)
                                        and len(line) >= 2
                                    ):
                                        text = line[1][0]
                                        text_lines.append(text)
                                page_text = "\n".join(text_lines)
                        elif isinstance(result, dict):
                            if "data" in result:
                                texts = result["data"]
                                if texts:
                                    page_text = "\n".join(
                                        [
                                            t[1][0]
                                            if isinstance(t, list) and len(t) >= 2
                                            else str(t)
                                            for t in texts
                                        ]
                                    )
                except Exception as e:
                    paddle_logging.warning(f"PaddleOCR failed for page {page_num}: {e}")
                    page_text = ""
                finally:
                    try:
                        os.remove(tmp_path)
                    except:
                        pass

                token_length = len(enc.encode(page_text))
                page_list.append((page_text, token_length))

            print(f"[PaddleOCR] Completed: extracted {len(page_list)} pages")
            print(f"\n[DEBUG] OCR completed, total pages: {len(page_list)}")
            return page_list

        except ImportError:
            paddle_logging.warning("PaddleOCR not installed, falling back to LLM OCR")
            return None
        except Exception as e:
            paddle_logging.warning(f"PaddleOCR extraction failed: {e}")
            return None

    def try_easyocr(pdf_path, max_pages=None, progress_callback=None, start_page=1):
        """Extract text from PDF using EasyOCR (free, deep learning OCR) with per-page progress callback"""
        try:
            import easyocr
            import cv2
            import numpy as np

            print(f"[EasyOCR] Initializing OCR model...")
            reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)

            doc = pymupdf.open(pdf_path)
            total_pages = len(doc)
            doc.close()

            pages_to_process = (
                total_pages if max_pages is None else min(max_pages, total_pages)
            )

            # Adjust for start_page (1-indexed)
            start_idx = start_page - 1
            remaining_pages = pages_to_process - start_idx

            if remaining_pages <= 0:
                print(f"[EasyOCR] All {pages_to_process} pages already cached")
                return []

            print(
                f"[EasyOCR] Processing pages {start_page}-{pages_to_process} ({remaining_pages} pages to go)..."
            )

            page_list = []

            for page_num in range(start_idx, pages_to_process):
                current_page = page_num + 1
                if page_num % 10 == 0 or page_num == start_idx:
                    print(
                        f"[EasyOCR] Processing page {current_page}/{pages_to_process}..."
                    )

                doc = pymupdf.open(pdf_path)
                page = doc[page_num]
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                img_data = pix.tobytes("png")
                doc.close()

                img_array = np.frombuffer(img_data, dtype=np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                result = reader.readtext(img, detail=0)
                page_text = "\n".join(result) if result else ""

                token_length = len(enc.encode(page_text))
                page_list.append((page_text, token_length))

                if progress_callback:
                    progress_callback(current_page, page_text, token_length)

            print(f"[EasyOCR] Completed: extracted {len(page_list)} pages")
            return page_list

        except ImportError:
            logging.warning("EasyOCR not installed, falling back to LLM OCR")
            return None
        except Exception as e:
            logging.warning(f"EasyOCR extraction failed: {e}")
            return None

    def extract_text_from_pdf_page_ocr(pdf_path, page_num, model="kimi-k2.5", max_retries=3):
        """Extract text from a single PDF page using LLM OCR with Kimi-2.5 VLM (default) or other models"""
        import base64
        import time

        for attempt in range(max_retries):
            try:
                doc = pymupdf.open(pdf_path)
                page = doc[page_num]

                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                img_data = pix.tobytes("png")
                img_base64 = base64.b64encode(img_data).decode("utf-8")
                doc.close()

                api_key = os.getenv("KIMI_API_KEY") or os.getenv("CHATGPT_API_KEY")
                base_url = "https://ark.cn-beijing.volces.com/api/coding/v3"

                message = {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "你是一个精准的 OCR 专家。请仔细阅读这张图片，提取其中的全部文字。直接输出结果，不要有任何解释。",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                        },
                    ],
                }

                import httpx
                client = httpx.Client(timeout=300.0)
                response = client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": model, "messages": [message], "temperature": 0, "max_tokens": 8192},
                )
                client.close()

                if response.status_code == 200:
                    result = response.json()
                    extracted_text = result["choices"][0]["message"]["content"]
                    tokens_used = result.get("usage", {}).get("total_tokens", 0)
                    print(f"[Kimi-OCR] Page {page_num + 1}: {tokens_used} tokens")
                    return extracted_text
                else:
                    logging.warning(f"Kimi OCR API error: {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"[Kimi-OCR] Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    return ""

            except Exception as e:
                error_str = str(e)
                if "ConnectionResetError" in error_str or "WriteError" in error_str or "ReadError" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"[Kimi-OCR] Connection reset, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                logging.warning(f"Kimi OCR failed for page {page_num}: {e}")
                return ""

        return ""

    def get_page_tokens_with_llm_ocr(pdf_path, max_pages=None, ocr_model="kimi-k2.5"):
        """Extract all pages using LLM OCR with Kimi-2.5 VLM (default)"""
        import time as time_module

        try:
            doc = pymupdf.open(pdf_path)
            total_pages = len(doc)
            doc.close()

            print(f"[LLM-OCR] Processing {total_pages} pages with {ocr_model}...")

            page_list = []
            pages_to_process = (
                total_pages if max_pages is None else min(max_pages, total_pages)
            )

            for page_num in range(pages_to_process):
                if page_num % 5 == 0:
                    print(
                        f"[LLM-OCR] Processing page {page_num + 1}/{pages_to_process}..."
                    )

                page_text = extract_text_from_pdf_page_ocr(pdf_path, page_num, model=ocr_model)
                token_length = len(enc.encode(page_text))
                page_list.append((page_text, token_length))

                if progress_callback:
                    progress_callback(page_num + 1, page_text, token_length)

                if page_num < pages_to_process - 1:
                    time_module.sleep(0.5)

            print(f"[LLM-OCR] Completed: extracted {len(page_list)} pages")
            return page_list

        except Exception as e:
            logging.warning(f"LLM OCR extraction failed: {e}")
            return None

    if pdf_parser == "PyPDF2":
        page_list = try_pypdf2(pdf_path, max_pages)
        if page_list and not needs_ocr(page_list):
            print(f"[PDF] Using PyPDF2, extracted {len(page_list)} pages")
            return page_list
    elif pdf_parser == "PyMuPDF":
        page_list = try_pymupdf(pdf_path, max_pages)
        if page_list and not needs_ocr(page_list):
            print(f"[PDF] Using PyMuPDF, extracted {len(page_list)} pages")
            return page_list

    print(f"[PDF] Trying PyPDF2 first...")
    page_list = try_pypdf2(pdf_path, max_pages)

    if page_list and not needs_ocr(page_list):
        print(f"[PDF] Using PyPDF2, extracted {len(page_list)} pages")
        return page_list

    print(f"[PDF] PyPDF2 extracted insufficient text, trying PyMuPDF...")
    page_list = try_pymupdf(pdf_path, max_pages)

    if page_list and not needs_ocr(page_list):
        print(f"[PDF] Using PyMuPDF, extracted {len(page_list)} pages")
        return page_list

    print(f"[PDF] PyPDF2/PyMuPDF extracted insufficient text, trying Kimi-2.5 VLM OCR...")

    ocr_model = os.getenv("KIMI_OCR_MODEL", "kimi-k2.5")
    page_list = get_page_tokens_with_llm_ocr(pdf_path, max_pages, ocr_model=ocr_model)

    if page_list and not needs_ocr(page_list):
        print(f"[PDF] Kimi-2.5 VLM OCR extracted {len(page_list)} pages")

        # Merge with cached pages if resuming
        if cached_pages is not None:
            page_list = cached_pages + page_list
            print(
                f"[Cache] Merged {len(cached_pages)} cached + {len(page_list) - len(cached_pages)} new pages"
            )

        # 保存缓存
        if use_cache and not cache_file.exists():
            try:
                cache_data = {
                    "total_pages": len(page_list),
                    "timestamp": datetime.now().isoformat(),
                    "pages": [
                        {
                            "page_num": i + 1,
                            "text": text,
                            "tokens": tokens,
                            "text_length": len(text),
                        }
                        for i, (text, tokens) in enumerate(page_list)
                    ],
                }
                cache_file.write_text(
                    json.dumps(cache_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"[Cache] ✅ Saved OCR cache: {len(page_list)} pages")
            except Exception as e:
                print(f"[Cache] Failed to save cache: {e}")

        return page_list

    print(f"[PDF] Kimi-2.5 VLM OCR failed/insufficient, trying EasyOCR (free)...")

    # Pass start_page to resume from cached position
    page_list = try_easyocr(pdf_path, max_pages, progress_callback, start_page)

    if page_list and not needs_ocr(page_list):
        print(f"[PDF] EasyOCR extracted {len(page_list)} pages")

        # Merge with cached pages if resuming
        if cached_pages is not None:
            page_list = cached_pages + page_list
            print(
                f"[Cache] Merged {len(cached_pages)} cached + {len(page_list) - len(cached_pages)} new pages"
            )

        # 保存缓存
        if use_cache and not cache_file.exists():
            try:
                cache_data = {
                    "total_pages": len(page_list),
                    "timestamp": datetime.now().isoformat(),
                    "pages": [
                        {
                            "page_num": i + 1,
                            "text": text,
                            "tokens": tokens,
                            "text_length": len(text),
                        }
                        for i, (text, tokens) in enumerate(page_list)
                    ],
                }
                cache_file.write_text(
                    json.dumps(cache_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"[Cache] ✅ Saved OCR cache: {len(page_list)} pages")
            except Exception as e:
                print(f"[Cache] Failed to save cache: {e}")

        return page_list
    if page_list and not needs_ocr(page_list):
        print(f"[PDF] LLM OCR extracted {len(page_list)} pages")
        return page_list

    print(f"[PDF] All extraction methods failed")

    # Save to cache if enabled and we actually ran OCR
    if use_cache:
        # Only save if we actually did OCR work (not loaded from cache)
        # We can check by seeing if cache file exists now
        # If it doesn't exist, we just did OCR work
        if not cache_file.exists():
            try:
                cache_data = {
                    "total_pages": len(page_list),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "pages": [
                        {
                            "page_num": i + 1,
                            "text": text,
                            "tokens": tokens,
                            "text_length": len(text),
                        }
                        for i, (text, tokens) in enumerate(page_list)
                    ],
                }

                cache_file.write_text(
                    json.dumps(cache_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"[Cache] ✅ Saved OCR cache: {len(page_list)} pages")
            except Exception as e:
                print(f"[Cache] Failed to save cache: {e}")

    return page_list

    # Save to cache if enabled and we actually ran OCR
    # Check if we used EasyOCR (this is the main expensive part)
    if use_cache and len(page_list) > 0:
        # Only save if we actually did OCR work (not loaded from cache)
        # We can check by seeing if the cache file exists now
        # If it doesn't exist, we just did OCR work
        if not cache_file.exists():
            try:
                cache_data = {
                    "total_pages": len(page_list),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "pages": [
                        {
                            "page_num": i + 1,
                            "text": text,
                            "tokens": tokens,
                            "text_length": len(text),
                        }
                        for i, (text, tokens) in enumerate(page_list)
                    ],
                }

                cache_file.write_text(
                    json.dumps(cache_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"[Cache] ✅ Saved OCR cache: {len(page_list)} pages")
            except Exception as e:
                print(f"[Cache] Failed to save cache: {e}")

    return page_list


def get_text_of_pdf_pages(pdf_pages, start_page, end_page):
    text = ""
    for page_num in range(start_page - 1, end_page):
        text += pdf_pages[page_num][0]
    return text


def get_text_of_pdf_pages_with_labels(pdf_pages, start_page, end_page):
    text = ""
    for page_num in range(start_page - 1, end_page):
        text += f"<physical_index_{page_num + 1}>\n{pdf_pages[page_num][0]}\n<physical_index_{page_num + 1}>\n"
    return text


def get_number_of_pages(pdf_path):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    num = len(pdf_reader.pages)
    return num


def post_processing(structure, end_physical_index):
    # First convert page_number to start_index in flat list
    for i, item in enumerate(structure):
        item["start_index"] = item.get("physical_index")
        if i < len(structure) - 1:
            if structure[i + 1].get("appear_start") == "yes":
                item["end_index"] = structure[i + 1]["physical_index"] - 1
            else:
                item["end_index"] = structure[i + 1]["physical_index"]
        else:
            item["end_index"] = end_physical_index
    tree = list_to_tree(structure)
    if len(tree) != 0:
        return tree
    else:
        ### remove appear_start
        for node in structure:
            node.pop("appear_start", None)
            node.pop("physical_index", None)
        return structure


def clean_structure_post(data):
    if isinstance(data, dict):
        data.pop("page_number", None)
        data.pop("start_index", None)
        data.pop("end_index", None)
        if "nodes" in data:
            clean_structure_post(data["nodes"])
    elif isinstance(data, list):
        for section in data:
            clean_structure_post(section)
    return data


def remove_fields(data, fields=["text"]):
    if isinstance(data, dict):
        return {k: remove_fields(v, fields) for k, v in data.items() if k not in fields}
    elif isinstance(data, list):
        return [remove_fields(item, fields) for item in data]
    return data


def print_toc(tree, indent=0):
    for node in tree:
        print("  " * indent + node["title"])
        if node.get("nodes"):
            print_toc(node["nodes"], indent + 1)


def print_json(data, max_len=40, indent=2):
    def simplify_data(obj):
        if isinstance(obj, dict):
            return {k: simplify_data(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [simplify_data(item) for item in obj]
        elif isinstance(obj, str) and len(obj) > max_len:
            return obj[:max_len] + "..."
        else:
            return obj

    simplified = simplify_data(data)
    print(json.dumps(simplified, indent=indent, ensure_ascii=False))


def remove_structure_text(data):
    if isinstance(data, dict):
        data.pop("text", None)
        if "nodes" in data:
            remove_structure_text(data["nodes"])
    elif isinstance(data, list):
        for item in data:
            remove_structure_text(item)
    return data


def check_token_limit(structure, limit=110000):
    list = structure_to_list(structure)
    for node in list:
        num_tokens = count_tokens(node["text"], model="gpt-4o")
        if num_tokens > limit:
            print(f"Node ID: {node['node_id']} has {num_tokens} tokens")
            print("Start Index:", node["start_index"])
            print("End Index:", node["end_index"])
            print("Title:", node["title"])
            print("\n")


def convert_physical_index_to_int(data):
    print(f"[DEBUG] convert_physical_index_to_int called with type: {type(data)}")
    if isinstance(data, list):
        for i in range(len(data)):
            # Check if item is a dictionary and has 'physical_index' key
            if isinstance(data[i], dict) and "physical_index" in data[i]:
                original = data[i]["physical_index"]
                if isinstance(data[i]["physical_index"], str):
                    if data[i]["physical_index"].startswith("<physical_index_"):
                        data[i]["physical_index"] = int(
                            data[i]["physical_index"].split("_")[-1].rstrip(">").strip()
                        )
                        print(f"[DEBUG] Converted physical_index from '{original}' to {data[i]['physical_index']}")
                    elif data[i]["physical_index"].startswith("physical_index_"):
                        data[i]["physical_index"] = int(
                            data[i]["physical_index"].split("_")[-1].strip()
                        )
                        print(f"[DEBUG] Converted physical_index from '{original}' to {data[i]['physical_index']}")
    elif isinstance(data, str):
        if data.startswith("<physical_index_"):
            data = int(data.split("_")[-1].rstrip(">").strip())
        elif data.startswith("physical_index_"):
            data = int(data.split("_")[-1].strip())
        # Check data is int
        if isinstance(data, int):
            return data
        else:
            return None
    return data


def convert_page_to_int(data):
    for item in data:
        if "page" in item and isinstance(item["page"], str):
            try:
                item["page"] = int(item["page"])
            except ValueError:
                # Keep original value if conversion fails
                pass
    return data


def add_node_text(node, pdf_pages):
    if isinstance(node, dict):
        start_page = node.get("start_index")
        end_page = node.get("end_index")
        node["text"] = get_text_of_pdf_pages(pdf_pages, start_page, end_page)
        if "nodes" in node:
            add_node_text(node["nodes"], pdf_pages)
    elif isinstance(node, list):
        for index in range(len(node)):
            add_node_text(node[index], pdf_pages)
    return


def add_node_text_with_labels(node, pdf_pages):
    if isinstance(node, dict):
        start_page = node.get("start_index")
        end_page = node.get("end_index")
        node["text"] = get_text_of_pdf_pages_with_labels(
            pdf_pages, start_page, end_page
        )
        if "nodes" in node:
            add_node_text_with_labels(node["nodes"], pdf_pages)
    elif isinstance(node, list):
        for index in range(len(node)):
            add_node_text_with_labels(node[index], pdf_pages)
    return


async def generate_node_summary(node, opt=None):
    prompt = f"""You are given a part of a document, your task is to generate a description of the partial document about what are main points covered in the partial document.

    Partial Document Text: {node["text"]}
    
    Directly return the description, do not include any other text.
    """
    model = get_model_for_task("node_summary", opt)
    task_params = get_task_params("node_summary", opt)
    response = await ChatGPT_API_async(model, prompt, task_params=task_params)
    return response


async def generate_summaries_for_structure(structure, opt=None):
    nodes = structure_to_list(structure)
    tasks = [generate_node_summary(node, opt=opt) for node in nodes]
    summaries = await asyncio.gather(*tasks)

    for node, summary in zip(nodes, summaries):
        node["summary"] = summary
    return structure


def create_clean_structure_for_description(structure):
    """
    Create a clean structure for document description generation,
    excluding unnecessary fields like 'text'.
    """
    if isinstance(structure, dict):
        clean_node = {}
        # Only include essential fields for description
        for key in ["title", "node_id", "summary", "prefix_summary"]:
            if key in structure:
                clean_node[key] = structure[key]

        # Recursively process child nodes
        if "nodes" in structure and structure["nodes"]:
            clean_node["nodes"] = create_clean_structure_for_description(
                structure["nodes"]
            )

        return clean_node
    elif isinstance(structure, list):
        return [create_clean_structure_for_description(item) for item in structure]
    else:
        return structure


def generate_doc_description(structure, opt=None):
    prompt = f"""Your are an expert in generating descriptions for a document.
    You are given a structure of a document. Your task is to generate a one-sentence description for the document, which makes it easy to distinguish the document from other documents.
        
    Document Structure: {structure}
    
    Directly return the description, do not include any other text.
    """
    model = get_model_for_task("node_summary", opt)
    task_params = get_task_params("node_summary", opt)
    response = ChatGPT_API(model, prompt, task_params=task_params)
    return response


def reorder_dict(data, key_order):
    if not key_order:
        return data
    return {key: data[key] for key in key_order if key in data}


def format_structure(structure, order=None):
    if not order:
        return structure
    if isinstance(structure, dict):
        if "nodes" in structure:
            structure["nodes"] = format_structure(structure["nodes"], order)
        if not structure.get("nodes"):
            structure.pop("nodes", None)
        structure = reorder_dict(structure, order)
    elif isinstance(structure, list):
        structure = [format_structure(item, order) for item in structure]
    return structure


class ConfigLoader:
    def __init__(self, default_path: str = None):
        if default_path is None:
            default_path = Path(__file__).parent / "config.yaml"
        self._default_dict = self._load_yaml(default_path)

    @staticmethod
    def _load_yaml(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _validate_keys(self, user_dict):
        unknown_keys = set(user_dict) - set(self._default_dict)
        if unknown_keys:
            raise ValueError(f"Unknown config keys: {unknown_keys}")

    def load(self, user_opt=None) -> config:
        """
        Load the configuration, merging user options with default values.
        """
        if user_opt is None:
            user_dict = {}
        elif isinstance(user_opt, config):
            user_dict = vars(user_opt)
        elif isinstance(user_opt, dict):
            user_dict = user_opt
        else:
            raise TypeError("user_opt must be dict, config(SimpleNamespace) or None")

        self._validate_keys(user_dict)
        merged = {**self._default_dict, **user_dict}
        return config(**merged)
