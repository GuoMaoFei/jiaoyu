import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pageindex.page_index import (
    generate_toc_continue,
    generate_toc_init,
    extract_json,
    get_json_content,
)


class MockResult:
    def __init__(self, content, finish_reason):
        self.content = content
        self.finish_reason = finish_reason


def make_result(response_str, finish_reason="finished"):
    return (response_str, finish_reason)


class TestExtractJson:
    def test_valid_json(self):
        data = '[{"structure": "1", "title": "测试", "physical_index": "<physical_index_1>"}]'
        result = extract_json(data)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_json_with_code_block(self):
        data = '```json\n[{"structure": "1", "title": "测试"}]\n```'
        result = extract_json(data)
        assert isinstance(result, list)

    def test_incomplete_json_returns_empty_dict(self):
        data = '[{"structure": "1", "title": "第一章"}, {"structure": "1.1", "title": "第一节'
        result = extract_json(data)
        assert isinstance(result, dict)
        assert result == {}


class TestGetJsonContent:
    def test_strips_code_block(self):
        data = '```json\n[{"a": 1}]\n```'
        result = get_json_content(data)
        assert result == '[{"a": 1}]'

    def test_passthrough(self):
        data = '[{"a": 1}]'
        result = get_json_content(data)
        assert result == '[{"a": 1}]'


class TestGenerateTocContinue:
    @pytest.fixture
    def mock_api(self):
        with patch("pageindex.page_index.ChatGPT_API_with_finish_reason") as mock:
            yield mock

    @pytest.fixture
    def mock_utils(self):
        with patch("pageindex.page_index.count_tokens", return_value=100):
            with patch("pageindex.page_index.get_model_for_task", return_value="qwen-max"):
                with patch("pageindex.page_index.get_task_params", return_value={"temperature": 0}):
                    yield

    def test_finish_reason_finished_valid_json(self, mock_api, mock_utils):
        response = '[{"structure": "1", "title": "第一章", "physical_index": "<physical_index_1>"}]'
        mock_api.return_value = make_result(response, "finished")

        toc_content = []
        part = "这是文本内容"

        result = generate_toc_continue(toc_content, part)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["structure"] == "1"


    def test_api_error_raises(self, mock_api, mock_utils):
        mock_api.return_value = "Error"

        with pytest.raises(Exception, match="LLM API failed"):
            generate_toc_continue([], "text")

    def test_unexpected_finish_reason_raises(self, mock_api, mock_utils):
        mock_api.return_value = make_result('[]', "content_filtered")

        with pytest.raises(Exception, match="unexpected finish reason"):
            generate_toc_continue([], "text")

    def test_max_retries_exceeded_raises(self, mock_api, mock_utils):
        mock_api.return_value = make_result('[{"structure": "1", "title": "test"}', "max_output_reached")

        with pytest.raises(Exception, match="LLM API failed after max retries"):
            generate_toc_continue([], "text" * 10000)


class TestGenerateTocInit:
    @pytest.fixture
    def mock_api(self):
        with patch("pageindex.page_index.ChatGPT_API_with_finish_reason") as mock:
            yield mock

    @pytest.fixture
    def mock_utils(self):
        with patch("pageindex.page_index.get_model_for_task", return_value="qwen-max"):
            with patch("pageindex.page_index.get_task_params", return_value={"temperature": 0}):
                yield

    def test_init_finished_valid_json(self, mock_api, mock_utils):
        response = '[{"structure": "1", "title": "第一章", "physical_index": "<physical_index_1>"}]'
        mock_api.return_value = make_result(response, "finished")

        part = "第一章的内容"

        result = generate_toc_init(part)
        assert isinstance(result, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
