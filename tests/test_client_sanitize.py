import pytest
from utils.client import _sanitize_content


class TestSanitizeContent:
    def test_normal_text_unchanged(self):
        assert _sanitize_content("hello world") == "hello world"

    def test_chinese_text_unchanged(self):
        assert _sanitize_content("你好世界") == "你好世界"

    def test_tab_newline_cr_preserved(self):
        assert _sanitize_content("a\tb\nc\r") == "a\tb\nc\r"

    def test_x1a_removed(self):
        assert _sanitize_content("hello\x1aworld") == "helloworld"

    def test_null_byte_removed(self):
        assert _sanitize_content("a\x00b") == "ab"

    def test_multiple_control_chars_removed(self):
        result = _sanitize_content("a\x01b\x02c\x1ad\x7fe")
        assert result == "abcde"

    def test_empty_string(self):
        assert _sanitize_content("") == ""

    def test_only_control_chars(self):
        assert _sanitize_content("\x00\x01\x1a\x7f") == ""

    def test_mixed_content(self):
        text = "正常文本\x1a包含控制字符\x00和\t制表符\n换行"
        expected = "正常文本包含控制字符和\t制表符\n换行"
        assert _sanitize_content(text) == expected