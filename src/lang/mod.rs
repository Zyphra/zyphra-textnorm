//! Per-language grammar ports. Each submodule mirrors `text_normalization/<lang>/` file for file and exposes
//! `pub fn grammar() -> &'static dyn Grammar`. See `PORTING.md`.

pub mod common;

#[cfg(feature = "lang-de")]
pub mod de;
#[cfg(feature = "lang-en")]
pub mod en;
#[cfg(feature = "lang-es")]
pub mod es;
#[cfg(feature = "lang-fr")]
pub mod fr;
#[cfg(feature = "lang-it")]
pub mod it;
#[cfg(feature = "lang-ja")]
pub mod ja;
#[cfg(feature = "lang-ko")]
pub mod ko;
#[cfg(feature = "lang-pt")]
pub mod pt;
#[cfg(feature = "lang-zh")]
pub mod zh;

use crate::pipeline::Grammar;

/// The grammar of a NeMo language code (`None` when the code is unknown or its feature is off).
pub fn grammar(nemo: &str) -> Option<&'static dyn Grammar> {
    match nemo {
        #[cfg(feature = "lang-en")]
        "en" => Some(en::grammar()),
        #[cfg(feature = "lang-de")]
        "de" => Some(de::grammar()),
        #[cfg(feature = "lang-es")]
        "es" => Some(es::grammar()),
        #[cfg(feature = "lang-fr")]
        "fr" => Some(fr::grammar()),
        #[cfg(feature = "lang-it")]
        "it" => Some(it::grammar()),
        #[cfg(feature = "lang-pt")]
        "pt" => Some(pt::grammar()),
        #[cfg(feature = "lang-ja")]
        "ja" => Some(ja::grammar()),
        #[cfg(feature = "lang-zh")]
        "zh" => Some(zh::grammar()),
        #[cfg(feature = "lang-ko")]
        "ko" => Some(ko::grammar()),
        _ => None,
    }
}
