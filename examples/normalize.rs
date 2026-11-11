//! `cargo run --release --example normalize -- <language> <text>` (language: en, de, es, fr, it, pt, ja, zh, ko):
//! prints the normalized text.
//! `DEBUG_TAGS=1` also prints each grammar call's tagged string on stderr.

fn main() {
    let mut args = std::env::args().skip(1);
    let (Some(language), Some(text)) = (args.next(), args.next()) else {
        eprintln!("usage: normalize <language> <text>");
        std::process::exit(2);
    };
    println!("{}", zyphra_textnorm::normalize(&text, &language));
}
