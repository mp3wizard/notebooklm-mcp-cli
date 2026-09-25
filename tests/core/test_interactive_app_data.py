from unittest.mock import MagicMock

from notebooklm_tools.core.download import DownloadMixin


def test_reads_app_data_from_interactive_html():
    mixin = DownloadMixin(cookies={"SID": "x"}, csrf_token="t")
    mixin._get_artifact_content = MagicMock(
        return_value='<div data-app-data="{&quot;quiz&quot;: [{&quot;question&quot;: &quot;Q1&quot;}]}"></div>'
    )
    assert mixin.get_interactive_app_data("nb", "el") == {"quiz": [{"question": "Q1"}]}


def test_returns_none_without_content():
    mixin = DownloadMixin(cookies={"SID": "x"}, csrf_token="t")
    mixin._get_artifact_content = MagicMock(return_value=None)
    assert mixin.get_interactive_app_data("nb", "el") is None
