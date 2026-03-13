import json

from discli.utils import format_output


def test_format_output_plain():
    result = format_output("hello world", use_json=False)
    assert result == "hello world"


def test_format_output_json_dict():
    data = {"key": "value"}
    result = format_output(data, use_json=True)
    assert json.loads(result) == data


def test_format_output_json_list():
    data = [{"id": 1}, {"id": 2}]
    result = format_output(data, use_json=True)
    assert json.loads(result) == data
