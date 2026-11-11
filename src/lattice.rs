//! The tagger: the shortest path through `text @ ClassifyFst` without an FST.
//!
//! Every `tokenize_and_classify.py` is a regular language over three kinds of items — a classified token (`T`), a
//! punctuation token (`P`, en-family only; zh/ja/ko list punctuation among their classifiers) and a whitespace run
//! (`W`, deleted or turned into one space; the parser ignores it). Each language's [`Shape`] is that language as a
//! small automaton; the Viterbi runs over `(position, automaton state)` with every candidate span every classifier
//! accepts. Costs are exact tropical sums. Among equal-cost paths the one with fewer items whose span holds a digit
//! (Unicode `Nd`) wins: a number is read as one token wherever the grammar allows it (the oracle broke these ties by
//! its compiled arc order; PORTING.md, "Ties"). Then the lower summed `rank`, then the first-found path.

use crate::text::{Cost, is_nemo_space, nd_range_start};

/// One accepted span of a classifier starting at the queried position.
#[derive(Clone, Debug, Default)]
pub struct Candidate {
    /// Exclusive end (char index).
    pub end: usize,
    /// The classifier's top-level weight plus every internal weight on the path.
    pub cost: Cost,
    /// Tie-break among equal-cost candidates, lower wins (see the module docs).
    pub rank: i32,
    /// The tagger's output for the span exactly as the FST writes it inside `tokens { … }`, e.g.
    /// `cardinal { integer: "one" }` or `name: "hello"`. Multi-token outputs (en money ranges) contain the
    /// literal `} tokens { ` joins the FST inserts.
    pub tag: String,
}

/// A union branch of `classify` (or the punctuation item).
pub trait Classifier: Send + Sync {
    /// Push every span accepted at `start` (all outputs when the FST is non-functional). `text` is the stripped
    /// input as chars; `end > start` always.
    fn candidates(&self, text: &[char], start: usize, out: &mut Vec<Candidate>);
    /// Fill in the `tag` of a candidate this classifier pushed at `start`, once it is on the best path. Classifiers
    /// that write the tag in `candidates` keep the default (no-op); one that leaves `tag` empty there rebuilds it
    /// here from `(start, end, cost, rank)`, which must then identify the candidate among those it pushed at `start`.
    fn materialize(&self, _text: &[char], _start: usize, _candidate: &mut Candidate) {}
}

/// The top-level structure of a language's `tokenize_and_classify.py`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Shape {
    /// en, es: `delete_space (TPP (WS | " " PUNCT " ") TPP)* delete_space | PUNCT` with
    /// `PUNCT = (WS | " "? P)+`, `TPP = (PUNCT " ")* T (" " PUNCT)*`: any T/P/W sequence without two adjacent T.
    En,
    /// de, it: `delete_space TPP (WS? TPP)* delete_space`, `TPP = (P " ")* T (" " P)*`, `P` a single punctuation
    /// token: W-free chunks each holding at least one T.
    De,
    /// fr: like `De` with en-style `PUNCT` closures (W inside TPP) and `| PUNCT`: any T/P/W sequence.
    Fr,
    /// ko: `delete_space T ((WS | "") T)* delete_space`.
    Ko,
    /// pt: `delete_space (T (WS T)* | P) delete_space` — no punctuation splitting next to tokens.
    Pt,
    /// zh, ja: `(tokens { classify } )+`, no whitespace handling.
    Cjk,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Token,
    Punct,
    Ws,
}

impl Shape {
    /// The automaton: next state after an item of `kind` from `state`, if legal.
    fn step(self, state: u8, kind: Kind) -> Option<u8> {
        use Kind::*;
        match self {
            // 0: start / after P or W, 1: after T
            Shape::En => match (kind, state) {
                (Token, 0) => Some(1),
                (Token, _) => None,
                (Punct | Ws, _) => Some(0),
            },
            // 0: start, 1: chunk without T, 2: chunk with T, 3: after an inner W
            Shape::De => match (kind, state) {
                (Token, _) => Some(2),
                (Punct, 0 | 1 | 3) => Some(1),
                (Punct, _) => Some(2),
                (Ws, 0) => Some(0),
                (Ws, 2 | 3) => Some(3),
                (Ws, _) => None,
            },
            Shape::Fr => Some(0),
            // 0: start, 1: after T, 2: after an inner W
            Shape::Ko => match (kind, state) {
                (Token, _) => Some(1),
                (Ws, 0) => Some(0),
                (Ws, 1 | 2) => Some(2),
                (Ws, _) => None,
                (Punct, _) => None,
            },
            // 0: start (W allowed), 1: after T, 2: after an inner W (needs T), 3: after the lone P, 4: trailing W
            Shape::Pt => match (kind, state) {
                (Token, 0 | 2) => Some(1),
                (Ws, 0) => Some(0),
                (Ws, 1) => Some(2),
                (Punct, 0) => Some(3),
                (Ws, 3 | 4) => Some(4),
                _ => None,
            },
            Shape::Cjk => match kind {
                Token => Some(0),
                Punct | Ws => None,
            },
        }
    }

    fn accepts(self, state: u8) -> bool {
        match self {
            Shape::En | Shape::Fr | Shape::Cjk => true,
            Shape::De => matches!(state, 2 | 3),
            Shape::Ko => matches!(state, 1 | 2),
            Shape::Pt => matches!(state, 1 | 2 | 3 | 4),
        }
    }

    fn has_ws(self) -> bool {
        !matches!(self, Shape::Cjk)
    }

    /// The automaton's state count (the lattice's cells per position).
    fn nstates(self) -> usize {
        match self {
            Shape::Fr | Shape::Cjk => 1,
            Shape::En => 2,
            Shape::Ko => 3,
            Shape::De => 4,
            Shape::Pt => 5,
        }
    }
}

/// One item of the best path.
#[derive(Clone, Debug)]
pub struct Item {
    pub kind: Kind,
    pub start: usize,
    pub end: usize,
    /// Present for `Token` and `Punct`.
    pub candidate: Option<Candidate>,
}

#[derive(Clone, Copy)]
struct Cell {
    cost: Cost,
    /// Items on the path whose span holds a digit.
    digits: u32,
    rank: i64,
    prev_pos: u32,
    prev_state: u8,
    /// Index into the candidate arena, or `NONE` for whitespace.
    item: u32,
    kind: Kind,
}

impl Cell {
    fn key(&self) -> (Cost, u32, i64) {
        (self.cost, self.digits, self.rank)
    }
}

const NONE: u32 = u32::MAX;
/// `owner` of an arena entry the punctuation item pushed.
const PUNCT: u16 = u16::MAX;

/// No path through the tagger (the oracle's `FstOpError` on the empty lattice).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NoPath;

/// `best_path`'s work buffers, kept per thread between calls. Taken out for the call (a nested call starts empty).
#[derive(Default)]
struct Work {
    cells: Vec<Option<Cell>>,
    digit_count: Vec<u32>,
    arena: Vec<Candidate>,
    /// which classifier pushed each arena entry (`PUNCT` for the punctuation item), for `materialize`
    owner: Vec<u16>,
    scratch: Vec<Candidate>,
    /// (kind, end, cost, rank, arena index)
    atoms: Vec<(Kind, usize, Cost, i64, u32)>,
}

thread_local! {
    static WORK: std::cell::Cell<Work> = std::cell::Cell::new(Work::default());
}

/// The lattice inputs of one language.
pub struct Tagger<'a> {
    pub shape: Shape,
    pub classifiers: &'a [Box<dyn Classifier>],
    pub punct: Option<&'a dyn Classifier>,
}

impl Tagger<'_> {
    /// The best item sequence covering all of `text`.
    pub fn best_path(&self, text: &[char]) -> Result<Vec<Item>, NoPath> {
        let mut work = WORK.take();
        let result = self.best_path_in(text, &mut work);
        work.arena.clear();
        work.scratch.clear();
        WORK.set(work);
        result
    }

    fn best_path_in(&self, text: &[char], work: &mut Work) -> Result<Vec<Item>, NoPath> {
        let Work { cells, digit_count, arena, owner, scratch, atoms } = work;
        let n = text.len();
        let ns_count = self.shape.nstates();
        cells.clear();
        cells.resize((n + 1) * ns_count, None);
        cells[0] =
            Some(Cell { cost: 0, digits: 0, rank: 0, prev_pos: u32::MAX, prev_state: 0, item: NONE, kind: Kind::Ws });
        // digit_count[i]: digits in text[..i]
        digit_count.clear();
        digit_count.push(0);
        for &c in text {
            digit_count.push(digit_count.last().unwrap() + nd_range_start(c).is_some() as u32);
        }
        arena.clear();
        owner.clear();
        for pos in 0..n {
            let base = pos * ns_count;
            if cells[base..base + ns_count].iter().all(Option::is_none) {
                continue;
            }
            atoms.clear();
            // whitespace run (maximal)
            if self.shape.has_ws() && is_nemo_space(text[pos]) && (pos == 0 || !is_nemo_space(text[pos - 1])) {
                let mut end = pos;
                while end < n && is_nemo_space(text[end]) {
                    end += 1;
                }
                atoms.push((Kind::Ws, end, 0, 0, NONE));
            }
            if let Some(p) = self.punct {
                scratch.clear();
                p.candidates(text, pos, scratch);
                for c in scratch.drain(..) {
                    if c.end > pos && c.end <= n {
                        atoms.push((Kind::Punct, c.end, c.cost, c.rank as i64, arena.len() as u32));
                        arena.push(c);
                        owner.push(PUNCT);
                    }
                }
            }
            for (ci, cl) in self.classifiers.iter().enumerate() {
                scratch.clear();
                cl.candidates(text, pos, scratch);
                for c in scratch.drain(..) {
                    if c.end > pos && c.end <= n {
                        let rank = ci as i64 * 1000 + c.rank as i64;
                        atoms.push((Kind::Token, c.end, c.cost, rank, arena.len() as u32));
                        arena.push(c);
                        owner.push(ci as u16);
                    }
                }
            }
            for s in 0..ns_count {
                let Some(cur) = cells[base + s] else { continue };
                for &(kind, end, cost, rank, idx) in atoms.iter() {
                    let Some(ns) = self.shape.step(s as u8, kind) else { continue };
                    let cand = Cell {
                        cost: cur.cost + cost,
                        digits: cur.digits + (digit_count[end] > digit_count[pos]) as u32,
                        rank: cur.rank + rank,
                        prev_pos: pos as u32,
                        prev_state: s as u8,
                        item: idx,
                        kind,
                    };
                    let slot = &mut cells[end * ns_count + ns as usize];
                    match slot {
                        Some(old) if old.key() <= cand.key() => {}
                        _ => *slot = Some(cand),
                    }
                }
            }
        }

        let mut best: Option<(u8, Cell)> = None;
        for s in 0..ns_count as u8 {
            if !self.shape.accepts(s) {
                continue;
            }
            if let Some(c) = cells[n * ns_count + s as usize] {
                if best.is_none_or(|(_, b)| c.key() < b.key()) {
                    best = Some((s, c));
                }
            }
        }
        let Some((mut state, _)) = best else { return Err(NoPath) };
        let mut len = 0;
        let (mut p, mut s) = (n, state);
        while let Some(cell) = cells[p * ns_count + s as usize].filter(|c| c.prev_pos != u32::MAX) {
            len += 1;
            (p, s) = (cell.prev_pos as usize, cell.prev_state);
        }
        let mut pos = n;
        let mut items = Vec::with_capacity(len);
        loop {
            let cell = cells[pos * ns_count + state as usize].expect("back-pointer chain");
            if cell.prev_pos == u32::MAX {
                break;
            }
            // each arena entry is on the path at most once (one item per start position): move it out
            let start = cell.prev_pos as usize;
            let candidate = (cell.item != NONE).then(|| {
                let i = cell.item as usize;
                let mut c = std::mem::take(&mut arena[i]);
                let cl: &dyn Classifier = match owner[i] {
                    PUNCT => self.punct.expect("punct owner"),
                    ci => self.classifiers[ci as usize].as_ref(),
                };
                cl.materialize(text, start, &mut c);
                c
            });
            items.push(Item { kind: cell.kind, start, end: pos, candidate });
            pos = cell.prev_pos as usize;
            state = cell.prev_state;
        }
        items.reverse();
        Ok(items)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Word;
    impl Classifier for Word {
        fn candidates(&self, text: &[char], start: usize, out: &mut Vec<Candidate>) {
            let mut end = start;
            while end < text.len() && !is_nemo_space(text[end]) && text[end] != ',' {
                end += 1;
                out.push(Candidate {
                    end,
                    cost: 100,
                    rank: 0,
                    tag: format!("name: \"{}\"", text[start..end].iter().collect::<String>()),
                });
            }
        }
    }
    struct Comma;
    impl Classifier for Comma {
        fn candidates(&self, text: &[char], start: usize, out: &mut Vec<Candidate>) {
            if text[start] == ',' {
                out.push(Candidate { end: start + 1, cost: 2, rank: 0, tag: "name: \",\"".into() });
            }
        }
    }

    fn tags(shape: Shape, s: &str) -> Result<Vec<String>, NoPath> {
        let cls: Vec<Box<dyn Classifier>> = vec![Box::new(Word)];
        let t = Tagger { shape, classifiers: &cls, punct: Some(&Comma) };
        let chars: Vec<char> = s.chars().collect();
        Ok(t.best_path(&chars)?.into_iter().filter_map(|i| i.candidate.map(|c| c.tag)).collect())
    }

    #[test]
    fn en_shape_keeps_words_whole_and_splits_punct() {
        assert_eq!(tags(Shape::En, "ab cd,").unwrap(), ["name: \"ab\"", "name: \"cd\"", "name: \",\""]);
        assert_eq!(tags(Shape::En, ",").unwrap(), ["name: \",\""]);
    }

    #[test]
    fn de_shape_needs_a_token_per_chunk() {
        assert!(tags(Shape::De, "ab ,").is_err());
        assert_eq!(tags(Shape::De, "ab, cd").unwrap().len(), 3);
    }

    #[test]
    fn every_reachable_state_fits_the_shape() {
        for shape in [Shape::En, Shape::De, Shape::Fr, Shape::Ko, Shape::Pt, Shape::Cjk] {
            let n = shape.nstates() as u8;
            for state in 0..n {
                for kind in [Kind::Token, Kind::Punct, Kind::Ws] {
                    if let Some(next) = shape.step(state, kind) {
                        assert!(next < n, "{shape:?}: {state} --{kind:?}--> {next}");
                    }
                }
            }
            // every state below the count is reachable from 0 (the count is not larger than needed)
            let mut seen = vec![false; n as usize];
            let mut stack = vec![0u8];
            while let Some(s) = stack.pop() {
                if !std::mem::replace(&mut seen[s as usize], true) {
                    stack.extend([Kind::Token, Kind::Punct, Kind::Ws].iter().filter_map(|&k| shape.step(s, k)));
                }
            }
            assert!(seen.iter().all(|&s| s), "{shape:?}: unreachable states");
        }
    }
}
