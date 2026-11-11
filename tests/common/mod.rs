//! Reading the committed goldens (`tests/golden/<name>.jsonl.zst`, written by `oracle/` and compressed with
//! `zstd -19`).

use std::io::Read;
use std::path::PathBuf;

pub fn tests_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests")
}

/// The decompressed lines of `golden/<name>.jsonl.zst`.
pub fn golden_lines(name: &str) -> Vec<String> {
    let path = tests_dir().join("golden").join(format!("{name}.jsonl.zst"));
    let file = std::fs::File::open(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    let mut decoder = ruzstd::decoding::StreamingDecoder::new(std::io::BufReader::new(file))
        .unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    let mut text = String::new();
    decoder.read_to_string(&mut text).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    text.lines().map(str::to_string).collect()
}
