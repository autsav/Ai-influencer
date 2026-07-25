from unittest.mock import MagicMock, patch

import pytest

from aeloria.generation.carousel import generate_carousel, carousel_slide_texts


def _brief(**kw):
    b = {
        "id": "b1", "slot_day": "2026-07-20", "content_format": "carousel",
        "prompt_seed": "forest morning guide", "slot_type": "static",
        "distribution_plan": {"on_screen_keywords": ["wake slow", "breathe", "tea", "walk"]},
    }
    b.update(kw)
    return b


def _settings():
    s = MagicMock()
    s.face_gate_threshold = 0.3
    s.realism_lora_url = ""
    s.refine_enabled = False
    s.carousel_max_slides = 7
    s.carousel_default_slides = 4
    return s


def _img(nbytes=b"png"):
    r = MagicMock()
    r.image_bytes = nbytes
    r.cost_usd = 0.05
    r.gen_params = {"model": "flux"}
    return r


def test_slide_texts_from_keywords_clamped():
    assert carousel_slide_texts(_brief(), 7, 4) == ["wake slow", "breathe", "tea", "walk"]
    many = _brief(distribution_plan={"on_screen_keywords": [str(i) for i in range(10)]})
    assert len(carousel_slide_texts(many, 7, 4)) == 7  # clamp to max


def test_slide_texts_defaults_when_no_keywords():
    b = _brief(distribution_plan={})
    assert len(carousel_slide_texts(b, 7, 4)) == 4  # default count, empty overlays
    assert carousel_slide_texts(b, 7, 4) == ["", "", "", ""]


@patch("aeloria.generation.carousel.overlay_image_text", side_effect=lambda b, t, s: b + b"|" + t.encode())
@patch("aeloria.generation.carousel.passes_gate", return_value=(0.9, True))
@patch("aeloria.generation.carousel.generate_image")
@patch("aeloria.generation.carousel.check_budget")
@patch("aeloria.generation.carousel.build_prompt", return_value="PROMPT")
def test_generate_carousel_makes_one_asset_per_slide(mock_bp, mock_cb, mock_gi, mock_pg, mock_ov):
    mock_gi.return_value = _img()
    db = MagicMock()
    db.insert.side_effect = lambda t, row: {**row, "id": f"a{db.insert.call_count}"}
    r2 = MagicMock(); r2.upload.return_value = "https://r2/x.png"
    out = generate_carousel(_brief(), db, _settings(), r2, MagicMock(), [0.1])
    assert len(out) == 4
    assert mock_gi.call_count == 4
    assert mock_cb.call_count == 4  # budget checked before each slide
    kinds = [c.args[1]["kind"] for c in db.insert.call_args_list]
    assert kinds == ["image"] * 4


@patch("aeloria.generation.carousel.overlay_image_text", side_effect=lambda b, t, s: b)
@patch("aeloria.generation.carousel.refine_and_regate", return_value=(b"refined-slide", 0.7))
@patch("aeloria.generation.carousel.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.carousel.generate_image")
@patch("aeloria.generation.carousel.check_budget")
@patch("aeloria.generation.carousel.build_prompt", return_value="PROMPT")
def test_carousel_refines_each_slide(mock_bp, mock_cb, mock_gi, mock_pg, mock_refine, mock_ov):
    mock_gi.return_value = _img(b"base-slide")
    db = MagicMock()
    db.insert.side_effect = lambda t, row: {**row, "id": "a1"}
    r2 = MagicMock(); r2.upload.return_value = "https://r2/x.png"
    s = _settings(); s.refine_enabled = True
    generate_carousel(_brief(), db, s, r2, MagicMock(), [0.1])
    assert mock_refine.call_count == 4                     # every slide refined
    assert mock_ov.call_args.args[0] == b"refined-slide"   # refined bytes flow to overlay/upload
    r2.upload.assert_called()


@patch("aeloria.generation.carousel.passes_gate", return_value=(0.1, False))
@patch("aeloria.generation.carousel.generate_image")
@patch("aeloria.generation.carousel.check_budget")
@patch("aeloria.generation.carousel.build_prompt", return_value="PROMPT")
def test_first_slide_gate_failure_aborts(mock_bp, mock_cb, mock_gi, mock_pg):
    mock_gi.return_value = _img()
    db = MagicMock()
    db.insert.side_effect = lambda t, row: {**row, "id": "a1"}
    r2 = MagicMock(); r2.upload.return_value = "https://r2/x.png"
    out = generate_carousel(_brief(), db, _settings(), r2, MagicMock(), [0.1])
    assert out == []
    assert mock_gi.call_count == 1  # aborted after first slide
