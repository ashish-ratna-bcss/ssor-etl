#!/usr/bin/env python3
"""Stdlib self-check for section_matcher -- run directly, no pytest.

Every input string here was pulled live from the CCTNS crimes API (see
plan doc / conversation) -- not invented. Run: python3 test_section_matcher.py
"""
from section_matcher import extract_sections, normalize_section_code


def test_normalize_section_code():
    assert normalize_section_code('64(2)(m)') == '64'
    assert normalize_section_code('66-D') == '66D'
    assert normalize_section_code('67A') == '67A'
    assert normalize_section_code('5(l)') == '5'
    assert normalize_section_code('137(2)') == '137'


def test_extract_sections_real_samples():
    assert extract_sections(
        '354B IPC, 354C IPC, 506 IPC, 509 IPC, 67A ITA-2000-2008'
    ) == [('IT_ACT', '67A')]

    assert extract_sections('64(2)(m) BNS, 78 BNS, 137(2) BNS') == [
        ('BNS', '64'), ('BNS', '78'), ('BNS', '137'),
    ]

    assert extract_sections(
        '5 POCSO ACT 2012, r/w 6 POCSO ACT 2012, 3(2)(v) SC ST POA ACT 2015'
    ) == [('POCSO', '5'), ('POCSO', '6')]

    assert extract_sections('332,196 BNS') == [('BNS', '332'), ('BNS', '196')]

    assert extract_sections('413,414 IPC, 317(4),317(5) BNS') == [
        ('BNS', '317'), ('BNS', '317'),
    ]

    assert extract_sections('66-D ITA-2000-2008, 318(4) BNS') == [
        ('IT_ACT', '66D'), ('BNS', '318'),
    ]

    # Anomalous source data ("BNSS BNS" combined token) -- no clean section
    # immediately precedes a real act marker, so this must yield nothing
    # rather than guess.
    assert extract_sections('175 BNSS BNS') == []

    assert extract_sections('') == []
    assert extract_sections(None) == []


def test_extract_sections_matches_ssor_kb_shape():
    # 67A ITA-2000-2008 is a real BLUE-tier hit -- confirms the parser's
    # output shape lines up with ssor_kb's (act_name, section_code) keys.
    pairs = extract_sections('354B IPC, 67A ITA-2000-2008')
    assert ('IT_ACT', '67A') in pairs


if __name__ == '__main__':
    test_normalize_section_code()
    test_extract_sections_real_samples()
    test_extract_sections_matches_ssor_kb_shape()
    print('OK')
