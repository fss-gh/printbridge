"""Tests for TSPL label builders."""

from printbridge.tspl.label_builder import build_tspl_label
from printbridge.tspl.cut_label_builder import build_tspl_cut_label


def test_label_builder_basic():
    result = build_tspl_label(
        product_name="Widget",
        width=100,
        height=50,
        label_width_mm=100,
        label_height_mm=60,
    )
    assert isinstance(result, bytes)
    assert b"SIZE 100 mm, 60 mm" in result
    assert b"PRINT 1,1" in result


def test_label_builder_includes_product_name():
    result = build_tspl_label(
        product_name="TestProduct",
        label_width_mm=100,
        label_height_mm=60,
    )
    assert b"TestProduct" in result


def test_label_builder_includes_qr_code():
    result = build_tspl_label(
        qr_url="https://example.com/123",
        label_width_mm=100,
        label_height_mm=60,
    )
    assert b"QRCODE" in result
    assert b"example.com" in result


def test_label_builder_includes_footer():
    result = build_tspl_label(
        label_width_mm=100,
        label_height_mm=60,
        footer_text="MyBrand",
    )
    assert b"MyBrand" in result


def test_label_builder_portrait_layout():
    result = build_tspl_label(
        label_width_mm=100,
        label_height_mm=150,
    )
    assert b"DIRECTION 1" in result


def test_label_builder_landscape_layout():
    result = build_tspl_label(
        label_width_mm=100,
        label_height_mm=60,
    )
    assert b"DIRECTION 0" in result


def test_cut_label_builder_basic():
    result = build_tspl_cut_label(
        profile_ref="2RF21",
        length=1200,
        label_width_mm=45,
        label_height_mm=35,
    )
    assert isinstance(result, bytes)
    assert b"SIZE 45 mm, 35 mm" in result
    assert b"PRINT 1" in result


def test_cut_label_builder_includes_length():
    result = build_tspl_cut_label(
        length=1200,
        cut_name="H",
        label_width_mm=45,
        label_height_mm=35,
    )
    assert b"1200" in result


def test_cut_label_builder_includes_footer():
    result = build_tspl_cut_label(
        order_ref="1245",
        label_width_mm=45,
        label_height_mm=35,
        footer_text="MyBrand",
    )
    assert b"MyBrand" in result


def test_cut_label_builder_includes_bin_number():
    result = build_tspl_cut_label(
        bin_number=3,
        label_width_mm=45,
        label_height_mm=35,
    )
    assert b'"5",0,1,1,"3"' in result
