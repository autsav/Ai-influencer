from unittest.mock import MagicMock, patch

import httpx

from aeloria.publishing.meta import publish_carousel


def _settings():
    s = MagicMock()
    s.graph_base = "https://graph.facebook.com/v23.0"
    s.ig_user_id = "IG"
    return s


def _resp(json):
    req = httpx.Request("POST", "https://graph.facebook.com/x")
    return httpx.Response(200, json=json, request=req)


@patch("aeloria.publishing.meta.token_store")
@patch("aeloria.publishing.meta._wait_finished")
@patch("aeloria.publishing.meta.httpx.Client")
def test_publish_carousel_builds_child_then_parent(mock_client_cls, mock_wait, mock_ts):
    mock_ts.get.return_value = "tok"
    c = mock_client_cls.return_value.__enter__.return_value
    # child1, child2, parent creation, then media_publish
    c.post.side_effect = [
        _resp({"id": "child1"}), _resp({"id": "child2"}),
        _resp({"id": "parent"}), _resp({"id": "MEDIA"}),
    ]
    cid, mid = publish_carousel(_settings(), ["u1", "u2"], "cap")
    assert (cid, mid) == ("parent", "MEDIA")
    # first two posts are carousel-item children
    child_calls = c.post.call_args_list[:2]
    for call in child_calls:
        assert call.kwargs["data"]["is_carousel_item"] == "true"
    # third post is the parent with media_type CAROUSEL + children
    parent_data = c.post.call_args_list[2].kwargs["data"]
    assert parent_data["media_type"] == "CAROUSEL"
    assert parent_data["children"] == "child1,child2"
    assert parent_data["caption"] == "cap"
