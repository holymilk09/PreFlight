"""Tests for the spatial (bounding-box) matching features and blended similarity."""

import pytest

from src.models import BoundingBox, StructuralFeatures
from src.services.template_matcher import (
    _RAW_FLOOR_BLENDED,
    _RAW_MATCH_ANCHOR_BLENDED,
    _RAW_NEW_ANCHOR_BLENDED,
    _blended_similarity,
    _calibrate_confidence,
    _classify_element,
    _extract_spatial_vector,
    _feature_similarity,
    _feature_vectors,
    _match_confidence,
)


def _box(x, y, w, h, element_type="text", order=0):
    return BoundingBox(
        x=x, y=y, width=w, height=h, element_type=element_type, confidence=0.9, reading_order=order
    )


def _features(boxes, page_count=1):
    return StructuralFeatures(
        element_count=max(1, len(boxes)),
        table_count=sum(1 for b in boxes if b.element_type == "table"),
        text_block_count=max(1, sum(1 for b in boxes if b.element_type == "text")),
        image_count=sum(1 for b in boxes if b.element_type in ("image", "figure")),
        page_count=page_count,
        text_density=0.4,
        layout_complexity=0.3,
        column_count=1,
        has_header=True,
        has_footer=True,
        bounding_boxes=boxes,
    )


class TestSpatialVector:
    def test_dimensions_and_range(self):
        vec = _extract_spatial_vector(_features([_box(0.1, 0.1, 0.3, 0.2)]))
        assert len(vec) == 27
        assert all(0.0 <= v <= 1.0 for v in vec)

    def test_empty_boxes_returns_none(self):
        assert _extract_spatial_vector(_features([])) is None

    def test_full_cell_coverage(self):
        """A table exactly covering grid cell (0,0) fills that cell only."""
        third = 1.0 / 3.0
        vec = _extract_spatial_vector(_features([_box(0.0, 0.0, third, third, "table")]))
        table_channel = vec[9:18]  # channels are text(0-8), table(9-17), image(18-26)
        assert table_channel[0] == pytest.approx(1.0)
        assert sum(table_channel[1:]) == pytest.approx(0.0)

    def test_overlap_splits_across_cells(self):
        """A box spanning two cells contributes its area to both, proportionally."""
        third = 1.0 / 3.0
        # Text box covering the full top row: 3 cells, each fully covered.
        vec = _extract_spatial_vector(_features([_box(0.0, 0.0, 1.0, third)]))
        text_channel = vec[0:9]
        assert text_channel[0] == pytest.approx(1.0)
        assert text_channel[1] == pytest.approx(1.0)
        assert text_channel[2] == pytest.approx(1.0)
        assert sum(text_channel[3:]) == pytest.approx(0.0)

    def test_page_count_normalizes(self):
        """The same overlay across 2 pages halves per-page occupancy."""
        third = 1.0 / 3.0
        one = _extract_spatial_vector(_features([_box(0.0, 0.0, third, third)], page_count=1))
        two = _extract_spatial_vector(_features([_box(0.0, 0.0, third, third)], page_count=2))
        assert two[0] == pytest.approx(one[0] / 2)

    def test_dense_overlap_clamps_to_one(self):
        boxes = [_box(0.0, 0.0, 1.0, 1.0) for _ in range(5)]
        vec = _extract_spatial_vector(_features(boxes))
        assert max(vec) == 1.0
        assert all(v <= 1.0 for v in vec)

    def test_channel_classification(self):
        assert _classify_element("TABLE") == "table"
        assert _classify_element("figure") == "image"
        assert _classify_element("picture") == "image"
        assert _classify_element("LAYOUT_WEIRD_VENDOR_TYPE") == "text"


class TestBlendedSimilarity:
    def test_identical_documents_full_confidence(self):
        f = _features([_box(0.1, 0.1, 0.4, 0.3, "table"), _box(0.2, 0.6, 0.5, 0.1)])
        vecs = _feature_vectors(f)
        raw, used_spatial = _blended_similarity(vecs, vecs)
        assert used_spatial is True
        assert raw == pytest.approx(1.0)
        assert _match_confidence(vecs, vecs) == pytest.approx(1.0)

    def test_fallback_when_either_side_lacks_boxes(self):
        """Legacy templates without boxes use the scalar path, not a penalty."""
        with_boxes = _feature_vectors(_features([_box(0.1, 0.1, 0.4, 0.3)]))
        without_boxes = _feature_vectors(_features([]))
        raw, used_spatial = _blended_similarity(with_boxes, without_boxes)
        assert used_spatial is False
        scalar_sim = _feature_similarity(with_boxes[0], without_boxes[0])
        assert raw == pytest.approx(scalar_sim)
        # Confidence equals the scalar calibration of the scalar similarity.
        assert _match_confidence(with_boxes, without_boxes) == pytest.approx(
            _calibrate_confidence(scalar_sim)
        )

    def test_blended_anchor_set_maps_to_documented_thresholds(self):
        assert _calibrate_confidence(
            _RAW_MATCH_ANCHOR_BLENDED,
            _RAW_MATCH_ANCHOR_BLENDED,
            _RAW_NEW_ANCHOR_BLENDED,
            _RAW_FLOOR_BLENDED,
        ) == pytest.approx(0.85)
        assert _calibrate_confidence(
            _RAW_NEW_ANCHOR_BLENDED,
            _RAW_MATCH_ANCHOR_BLENDED,
            _RAW_NEW_ANCHOR_BLENDED,
            _RAW_FLOOR_BLENDED,
        ) == pytest.approx(0.50)

    def test_spatial_difference_lowers_confidence(self):
        """Same scalars, different layout -> spatial signal must separate them."""
        top_table = _features([_box(0.0, 0.0, 0.5, 0.3, "table"), _box(0.1, 0.6, 0.4, 0.1)])
        bottom_table = _features([_box(0.4, 0.65, 0.5, 0.3, "table"), _box(0.5, 0.1, 0.4, 0.1)])
        conf_same = _match_confidence(_feature_vectors(top_table), _feature_vectors(top_table))
        conf_diff = _match_confidence(_feature_vectors(top_table), _feature_vectors(bottom_table))
        assert conf_diff < conf_same
        assert conf_diff < 0.85  # different layouts must not auto-MATCH
