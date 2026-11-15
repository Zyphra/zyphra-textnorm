// The core crate under another name: `zyphra_textnorm` here is the #[pymodule] function.
use ::zyphra_textnorm as core_tn;
use pyo3::prelude::*;

/// A text normalizer: the markup it keeps as typed, whether the pre-pass runs, and its memo.
#[pyclass(frozen, module = "zyphra_textnorm")]
struct Normalizer(core_tn::Normalizer);

#[pymethods]
impl Normalizer {
    #[new]
    #[pyo3(signature = (markup_tags=Vec::new(), prepass=false))]
    fn new(markup_tags: Vec<String>, prepass: bool) -> Self {
        Normalizer(core_tn::Normalizer::with_markup_tags(markup_tags).with_prepass(prepass))
    }

    #[getter]
    fn markup_tags(&self) -> Vec<String> {
        self.0.markup_tags().map(str::to_string).collect()
    }

    #[getter]
    fn prepass(&self) -> bool {
        self.0.prepass()
    }

    fn normalize(&self, py: Python<'_>, text: &str, language: &str) -> String {
        py.detach(|| self.0.normalize(text, language))
    }

    fn clear_memo(&self) {
        self.0.clear_memo();
    }
}

/// The spoken form of `text` in `language`, by a shared normalizer without markup tags.
#[pyfunction]
fn normalize(py: Python<'_>, text: &str, language: &str) -> String {
    py.detach(|| core_tn::normalize(text, language))
}

/// The pre-pass alone: the rewritten text and each rewrite as (rule, before, after). For inspecting the rules; the
/// normalizer runs it itself with `prepass=True`.
#[pyfunction]
#[pyo3(signature = (text, language, markup_tags=Vec::new()))]
fn prepass(
    py: Python<'_>,
    text: &str,
    language: &str,
    markup_tags: Vec<String>,
) -> (String, Vec<(String, String, String)>) {
    py.detach(|| {
        let (out, hits) = core_tn::prepass::apply(text, language, &markup_tags);
        (out, hits.into_iter().map(|h| (h.rule.to_string(), h.before, h.after)).collect())
    })
}

#[pyfunction]
fn collapse_line_breaks(text: &str) -> String {
    core_tn::collapse_line_breaks(text)
}

#[pyfunction]
fn supported(language: &str) -> bool {
    core_tn::supported(language)
}

#[pymodule]
fn zyphra_textnorm(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Normalizer>()?;
    m.add_function(wrap_pyfunction!(normalize, m)?)?;
    m.add_function(wrap_pyfunction!(collapse_line_breaks, m)?)?;
    m.add_function(wrap_pyfunction!(prepass, m)?)?;
    m.add("PREPASS_RULES", core_tn::prepass::ORDER.to_vec())?;
    m.add_function(wrap_pyfunction!(supported, m)?)?;
    m.add("LANGUAGES", core_tn::LANGUAGES.to_vec())?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
