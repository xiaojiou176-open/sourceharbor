from __future__ import annotations

from sqlalchemy import String

from apps.api.app.models.video import Video


def test_video_model_declares_content_type_column_with_video_default() -> None:
    column = Video.__table__.c.content_type

    assert isinstance(column.type, String)
    assert column.type.length == 32
    assert column.nullable is False
    assert column.default is not None
    assert column.default.arg == "video"
