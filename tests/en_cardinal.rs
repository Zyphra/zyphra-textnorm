//! The en number-name FARs and `CardinalFst().final_graph` against the oracle dump
//! (`tests/golden/en_cardinal_far.jsonl.zst`, `oracle/dump_en_cardinal_far.py`).
#![cfg(feature = "lang-en")]

mod common;

use serde::Deserialize;
use zyphra_textnorm::lang::en::taggers::cardinal::{
    best, final_graph_best, final_graph_outputs, number_name, number_name_au,
};

#[derive(Deserialize)]
struct Row {
    digits: String,
    graph: Option<String>,
    graph_au: Option<String>,
    #[serde(rename = "final")]
    final_: Option<String>,
}

#[test]
fn far_dump() {
    let mut bad = 0;
    for line in common::golden_lines("en_cardinal_far") {
        let r: Row = serde_json::from_str(&line).unwrap();
        let outs = final_graph_outputs(&r.digits);
        let got = (number_name(&r.digits), number_name_au(&r.digits), best(&outs).map(str::to_string));
        let fast = final_graph_best(&r.digits);
        if fast.as_ref().map(|f| f.0.as_str()) != best(&outs) || fast.map(|f| f.1) != outs.iter().map(|o| o.1).min() {
            bad += 1;
            eprintln!("{}: final_graph_best differs from final_graph_outputs", r.digits);
        }
        if got != (r.graph.clone(), r.graph_au.clone(), r.final_.clone()) {
            bad += 1;
            if bad <= 20 {
                eprintln!("{}: want {:?} {:?} {:?}\n  got {:?}", r.digits, r.graph, r.graph_au, r.final_, got);
            }
        }
    }
    assert_eq!(bad, 0);
}
