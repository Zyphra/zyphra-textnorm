/* zyphra-textnorm: text normalization for TTS (written form to spoken form). The C ABI of the Rust library, built
 * with its `capi` feature as a static library:
 *
 *   cargo rustc --release --lib --features capi --crate-type staticlib
 *
 * UTF-8 in (invalid sequences are replaced with U+FFFD), UTF-8 out. Every returned string is NUL-terminated, never
 * NULL, and owned by the caller, who releases it with zyphra_textnorm_free. All functions are thread-safe; calls on
 * one normalizer from several threads share its memo.
 */
#ifndef ZYPHRA_TEXTNORM_H
#define ZYPHRA_TEXTNORM_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct zyphra_textnorm zyphra_textnorm;

/* A normalizer that keeps the markup of `tags` as typed: a '\n'-separated list of tag names (`tags_len` bytes;
 * NULL / 0 keeps none). "laugh\nshouting" keeps <laugh/>, <laugh> and <shouting>...</shouting>. Released with
 * zyphra_textnorm_delete. */
zyphra_textnorm *zyphra_textnorm_new(const char *tags, size_t tags_len);

/* Release a normalizer (NULL is a no-op). */
void zyphra_textnorm_delete(zyphra_textnorm *tn);

/* The spoken form of `text` in `language` (a grammar language: en, de, es, fr, it, pt, ja, zh, ko). Memoized. Never
 * fails: a language without a grammar comes back with its line breaks collapsed, and a sentence the grammar fails on
 * is kept as typed. Line breaks are collapsed first; markup and verbatim spans (U+E000 ... U+E001) stay as typed. */
char *zyphra_textnorm_normalize(const zyphra_textnorm *tn, const char *text, size_t text_len, const char *language,
                                size_t language_len);

/* One plain space for every whitespace run that contains a line break, tab or other non-space whitespace. */
char *zyphra_textnorm_collapse_line_breaks(const char *text, size_t text_len);

/* 1 when this build has a grammar for `language`, else 0. */
int zyphra_textnorm_supported(const char *language, size_t language_len);

/* Release a string returned by this library (NULL is a no-op). */
void zyphra_textnorm_free(char *s);

#ifdef __cplusplus
}
#endif

#endif /* ZYPHRA_TEXTNORM_H */
