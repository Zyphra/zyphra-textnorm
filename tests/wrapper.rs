//! The wrapper layer through the public API (and the C ABI with `--features capi`). Expected strings are the oracle's
//! (`oracle/`).

use zyphra_textnorm::{Normalizer, collapse_line_breaks, normalize, supported};

#[test]
fn unsupported_language_only_collapses_line_breaks() {
    let tn = Normalizer::with_markup_tags(["laugh"]);
    assert_eq!(tn.normalize("a.\n\nb", "xx"), "a. b");
    assert_eq!(tn.normalize("keep  <laugh/>  $5", "en_us"), "keep  <laugh/>  $5");
    assert!(!supported("xx") && !supported("en_us") && supported("en") && supported("zh"));
}

#[test]
fn empty_and_whitespace_text() {
    assert_eq!(normalize("", "en"), "");
    assert_eq!(normalize("   ", "en"), "   ");
    assert_eq!(normalize(" \n ", "en"), " ");
    assert_eq!(collapse_line_breaks(" \n "), " ");
}

#[cfg(feature = "capi")]
#[test]
fn c_abi_round_trip() {
    use std::ffi::CStr;
    use zyphra_textnorm::ffi;

    let tags = "laugh\nshouting";
    let text = "a.\n\nb";
    // SAFETY: valid pointers and lengths; every result is freed with the library's free.
    unsafe {
        let tn = ffi::zyphra_textnorm_new(tags.as_ptr().cast(), tags.len());
        assert_eq!((*tn).markup_tags().collect::<Vec<_>>(), ["laugh", "shouting"]);
        let p = ffi::zyphra_textnorm_normalize(tn, text.as_ptr().cast(), text.len(), "xx".as_ptr().cast(), 2);
        assert_eq!(CStr::from_ptr(p).to_str().unwrap(), "a. b");
        ffi::zyphra_textnorm_free(p);
        let p = ffi::zyphra_textnorm_collapse_line_breaks(text.as_ptr().cast(), text.len());
        assert_eq!(CStr::from_ptr(p).to_str().unwrap(), "a. b");
        ffi::zyphra_textnorm_free(p);
        assert_eq!(ffi::zyphra_textnorm_supported("ko".as_ptr().cast(), 2), 1);
        assert_eq!(ffi::zyphra_textnorm_supported("k".as_ptr().cast(), 1), 0);
        // invalid UTF-8 is decoded lossily, never rejected
        let bad = [b'a', 0xff, b'\n', b'b'];
        let p = ffi::zyphra_textnorm_collapse_line_breaks(bad.as_ptr().cast(), bad.len());
        assert_eq!(CStr::from_ptr(p).to_str().unwrap(), "a\u{fffd} b");
        ffi::zyphra_textnorm_free(p);
        let p = ffi::zyphra_textnorm_normalize(tn, std::ptr::null(), 0, std::ptr::null(), 0);
        assert_eq!(CStr::from_ptr(p).to_bytes(), b"");
        ffi::zyphra_textnorm_free(p);
        ffi::zyphra_textnorm_delete(tn);
        let none = ffi::zyphra_textnorm_new(std::ptr::null(), 0);
        assert_eq!((*none).markup_tags().count(), 0);
        ffi::zyphra_textnorm_delete(none);
    }
}

#[cfg(feature = "lang-en")]
mod en {
    use zyphra_textnorm::Normalizer;

    #[test]
    fn sentence_retry_and_markup() {
        let tn = Normalizer::with_markup_tags(["laugh", "shouting"]);
        assert_eq!(tn.normalize("It costs $5.\nNext day.", "en"), "It costs five dollars. Next day.");
        assert_eq!(tn.normalize("So I said <laugh/> no way, $5.", "en"), "So I said <laugh/> no way, five dollars.");
        assert_eq!(tn.normalize("<shouting>Get out!</shouting>  ok", "en"), "<shouting>Get out!</shouting> ok");
        let g = "\u{e000}həˈloʊ\u{e001}";
        assert_eq!(tn.normalize(&format!("say  {g}  5"), "en"), format!("say  {g}  five"));
        assert_eq!(tn.normalize(&format!("say {g} <laugh/> 5 times"), "en"), format!("say {g} <laugh/> five times"));
    }
}

#[cfg(feature = "lang-ja")]
#[test]
fn only_the_given_tags_split_the_text() {
    // golden ja row: a kept marker splits the text and each side is normalized alone; read as text (no tags, or other
    // tags), the grammar has no path through `3日 <breath/>` and the sentence stays as typed.
    let text = "今日は3日 <breath/> です";
    assert_eq!(Normalizer::with_markup_tags(["breath"]).normalize(text, "ja"), "今日は三日 <breath/> です");
    assert_eq!(Normalizer::with_markup_tags(["laugh"]).normalize(text, "ja"), text);
    assert_eq!(normalize(text, "ja"), text);
}

#[cfg(feature = "lang-id")]
#[test]
fn repeated_currency_ranges_require_positive_endpoints() {
    let grammar = zyphra_textnorm::lang::grammar("id").unwrap();
    assert_eq!(
        zyphra_textnorm::pipeline::normalize(grammar, "$10-$20", false).unwrap(),
        "sepuluh dolar sampai dua puluh dolar"
    );
    for text in ["$10--$20", "$10-−$20", "$10-~$20", "$10-±$20"] {
        assert_eq!(zyphra_textnorm::pipeline::normalize(grammar, text, false).unwrap(), text);
    }
}

#[cfg(feature = "lang-ru")]
#[test]
fn russian_dates_keep_following_text() {
    assert_eq!(
        zyphra_textnorm::normalize("1 мая 2024 г. важный текст", "ru"),
        "первое мая две тысячи двадцать четвертого года важный текст"
    );
}

#[cfg(feature = "lang-vi")]
#[test]
fn vietnamese_approximation_materializes_selected_children() {
    for (text, expected) in [("~1.5", "khoảng một phẩy năm"), ("~1/2", "khoảng một phần hai")] {
        assert_eq!(zyphra_textnorm::normalize(text, "vi"), expected);
    }
}
