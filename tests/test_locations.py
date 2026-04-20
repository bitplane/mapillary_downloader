"""Tests for variant extraction from OSMNames rows."""

from mapillary_downloader.locations import get_variants


def test_chinese_city_with_english_wikipedia():
    row = {
        "name": "北京市",
        "wikipedia": "en:Beijing",
        "alternative_names": "Baekging,Beijing,Pechino,Pekin,Pékin,Peking,北平",
    }
    variants = get_variants(row)
    assert variants[0] == "北京市"
    assert variants[1] == "Beijing"
    # Col 3 should be a clean-ASCII alt that isn't already Beijing
    assert "Baekging" in variants or "Peking" in variants or "Pechino" in variants
    # Col 4 should be a diacritic alt
    assert any("é" in v or "è" in v or "í" in v for v in variants)


def test_russian_city_with_native_wikipedia():
    row = {
        "name": "Москва",
        "wikipedia": "ru:Москва",
        "alternative_names": "Maskava,Moscow,Moskau,Moskva,Московь",
    }
    variants = get_variants(row)
    assert variants[0] == "Москва"
    # No en: wiki, so col 2 is first clean-ASCII alt
    assert variants[1] == "Maskava"
    assert "Московь" not in variants


def test_pure_ascii_name():
    row = {
        "name": "Paris",
        "wikipedia": "fr:Paris",
        "alternative_names": "Parigi,París,Paris",
    }
    variants = get_variants(row)
    assert variants[0] == "Paris"
    # "Paris" in alts should dedup against native
    assert variants.count("Paris") == 1
    # Diacritic-only alt picked
    assert "París" in variants


def test_non_latin_alts_only():
    row = {
        "name": "东京",
        "wikipedia": "",
        "alternative_names": "トーキョー,东京都,도쿄",
    }
    variants = get_variants(row)
    assert variants == ["东京"]


def test_empty_alternative_names():
    row = {"name": "Neverville", "wikipedia": "", "alternative_names": ""}
    assert get_variants(row) == ["Neverville"]


def test_wikipedia_none():
    row = {"name": "Somewhere", "wikipedia": None, "alternative_names": None}
    assert get_variants(row) == ["Somewhere"]


def test_wiki_en_dedupe_against_name():
    row = {
        "name": "Beijing",
        "wikipedia": "en:Beijing",
        "alternative_names": "Pekin",
    }
    variants = get_variants(row)
    assert variants[0] == "Beijing"
    assert variants.count("Beijing") == 1
    assert "Pekin" in variants


def test_dedup_case_insensitive():
    row = {
        "name": "bangkok",
        "wikipedia": "en:Bangkok",
        "alternative_names": "BANGKOK,Bangkòk",
    }
    variants = get_variants(row)
    assert variants[0] == "bangkok"
    # Wiki "Bangkok" is a case-variant of native, should dedup
    assert len(variants) == 2
    assert variants[1] == "Bangkòk"


def test_alt_with_apostrophe_accepted():
    row = {
        "name": "西安市",
        "wikipedia": "",
        "alternative_names": "Xi'an,Tây An",
    }
    variants = get_variants(row)
    # Xi'an has an apostrophe but is a legit English name → should be accepted
    assert "Xi'an" in variants


def test_alt_with_period_accepted():
    row = {
        "name": "Санкт-Петербург",
        "wikipedia": "",
        "alternative_names": "St. Petersburg",
    }
    variants = get_variants(row)
    assert "St. Petersburg" in variants


def test_lowercase_alt_skipped():
    row = {
        "name": "上海市",
        "wikipedia": "",
        "alternative_names": "shanghai,Shanghai",
    }
    variants = get_variants(row)
    # lowercase 'shanghai' fails capitalisation check; 'Shanghai' wins
    assert "Shanghai" in variants
    assert "shanghai" not in variants


def test_mixed_script_alt_rejected():
    row = {
        "name": "上海市",
        "wikipedia": "",
        "alternative_names": "Shanghai市,Shanghai",
    }
    variants = get_variants(row)
    # Mixed-script entry rejected by _is_latin_script
    assert "Shanghai市" not in variants
    assert "Shanghai" in variants


def test_max_four_variants():
    row = {
        "name": "上海市",
        "wikipedia": "en:Shanghai",
        "alternative_names": "Sciangai,Shanghái,Szanghaj,Xangai",
    }
    variants = get_variants(row)
    assert len(variants) <= 4
    assert variants[0] == "上海市"
    assert variants[1] == "Shanghai"


def test_hyphenated_ascii_alt_accepted():
    row = {
        "name": "Saint-Étienne",
        "wikipedia": "",
        "alternative_names": "Saint-Etienne",
    }
    variants = get_variants(row)
    # Native has diacritic, alt is clean ASCII with hyphen
    assert variants == ["Saint-Étienne", "Saint-Etienne"]


def test_multi_word_ascii_alt_accepted():
    row = {
        "name": "القاهرة",
        "wikipedia": "",
        "alternative_names": "Cairo,Le Caire,El Cairo",
    }
    variants = get_variants(row)
    assert variants[0] == "القاهرة"
    # Cairo (single word, clean) should win tier-A, multi-word fallback if any
    assert "Cairo" in variants
