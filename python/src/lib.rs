// The core crate under another name: `zyphra_textnorm` here is the #[pymodule] function.
use ::zyphra_textnorm as core_tn;
use pyo3::prelude::*;

/// A text normalizer: the markup it keeps as typed and its memo.
#[pyclass(frozen, module = "zyphra_textnorm")]
struct Normalizer(core_tn::Normalizer);

#[pymethods]
impl Normalizer {
    #[new]
    #[pyo3(signature = (markup_tags=Vec::new()))]
    fn new(markup_tags: Vec<String>) -> Self {
        Normalizer(core_tn::Normalizer::with_markup_tags(markup_tags))
    }

    #[getter]
    fn markup_tags(&self) -> Vec<String> {
        self.0.markup_tags().map(str::to_string).collect()
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
    m.add_function(wrap_pyfunction!(supported, m)?)?;
    m.add("LANGUAGES", core_tn::LANGUAGES.to_vec())?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
