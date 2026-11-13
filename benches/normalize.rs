//! `cargo bench`: median wall time and heap allocations per call, memo miss and memo hit.
//! No harness dependency: a fixed number of timed calls per case on exactly the case's text; the memo is cleared
//! before each timed call (`Normalizer::clear_memo`, untimed), so every timed call is a miss on the plain sentence.
//! Every case runs untimed first (one-time table construction, cold caches and clocks), so the first case listed is
//! not timed colder than the rest.

use std::alloc::{GlobalAlloc, Layout, System};
use std::hint::black_box;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

struct Counting;

static ALLOCS: AtomicU64 = AtomicU64::new(0);

// SAFETY: forwards to the system allocator; only counts.
unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCS.fetch_add(1, Ordering::Relaxed);
        unsafe { System.alloc(layout) }
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { System.dealloc(ptr, layout) }
    }
    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        ALLOCS.fetch_add(1, Ordering::Relaxed);
        unsafe { System.realloc(ptr, layout, new_size) }
    }
}

#[global_allocator]
static GLOBAL: Counting = Counting;

const CASES: &[(&str, &str)] = &[
    ("en", "Call me at 123 Main Street, please."),
    (
        "en",
        "On Jan. 5, 2021 the company reported revenue of $3.5 million, up 12% from 2020; CEO Dr. Smith said the \
         3rd quarter starts at 9:30 a.m. EST and ends on 10/19. Contact sales@example.com or call (555) 123-4567 \
         for the 2 1/2 kg samples, the 1,250 units at 7.5 mph and the 24-hour support line. The 1990s were \
         different: 50 km/h, 3.14159 and -40 degrees were all in the 100-page report of the U.S.A. office.",
    ),
    ("de", "Am 3. Oktober 2026 um 10:30 Uhr kostete es 5,32 €."),
    ("es", "El 12/03/2021 a las 10:30 pagamos 1.250,50 €."),
    ("fr", "Le 15 mai 2021, il a payé 1 250,50 euros."),
    ("it", "Il 12/03/2021 alle 10:30 ho pagato 5,32 €."),
    ("pt", "Em 12/03/2021 às 10h30 paguei R$ 1.250,50."),
    ("ja", "2021年3月5日の10時30分に5.5ドルを払った。"),
    ("zh", "2021年3月5日10点30分他花了5.5元。"),
    ("ko", "2021년 3월 5일 10시 30분에 5,000원을 냈다."),
    ("nl", "Om 12:30 kostte 37 kg precies 125 euro."),
    ("pl", "O 12:30 kupiłem 37 kg za 125 zł."),
    ("tr", "Saat 12:30 için 37 kg ve 125 TL."),
    ("uk", "О 12:30 придбали 37 кг за 125 грн."),
    ("cs", "Ve 12:30 stálo 37 kg přesně 125 Kč."),
    ("da", "Klokken 12:30 kostede 37 kg i alt 125 kr."),
    ("fi", "Kello 12:30 ostin 37 kg hintaan 125 euroa."),
    ("el", "Στις 12:30 αγόρασα 37 κιλά για 125 ευρώ."),
    ("nb", "Klokken 12:30 kostet 37 kg i alt 125 kr."),
    ("ro", "La 12:30 am cumpărat 37 kg pentru 125 lei."),
    ("sk", "O 12:30 stálo 37 kg presne 125 eur."),
    ("bg", "В 12:30 купих 37 кг за 125 лв."),
    ("he", "בשעה 12:30 קניתי 37 קג במחיר 125 שח."),
    ("th", "เวลา 12:30 ซื้อ 37 กก ราคา 125 บาท"),
    ("tl", "Alas 12:30 bumili ng 37 kg sa 125 piso."),
    ("ms", "Pada 12:30 saya membeli 37 kg dengan 125 ringgit."),
    ("ka", "12:30 საათზე ვიყიდე 37 კგ 125 ლარად."),
    ("ta", "12:30 மணிக்கு 37 கிலோ விலை 125 ரூபாய்."),
    ("gu", "12:30 વાગ્યે 37 કિલો માટે 125 રૂપિયા."),
    ("kn", "12:30 ಗಂಟೆಗೆ 37 ಕಿಲೋ ಬೆಲೆ 125 ರೂಪಾಯಿ."),
    ("ml", "12:30 മണിക്ക് 37 കിലോ വില 125 രൂപ."),
    ("pa", "12:30 ਵਜੇ 37 ਕਿਲੋ ਦੀ ਕੀਮਤ 125 ਰੁਪਏ।"),
    ("or", "12:30 ବେଳେ 37 କିଲୋର ମୂଲ୍ୟ 125 ଟଙ୍କା।"),
    ("ru", "В 12:30 купили 37 кг за 125 рублей."),
    ("sv", "Klockan 12:30 kostade 37 kg totalt 125 kr."),
    ("hu", "12:30 órakor 37 kg ára összesen 125 Ft."),
    ("ar", "الساعة 12:30 ووزن 37 كجم بسعر 125 ريال."),
    ("vi", "Lúc 12:30 mua 37 kg với giá 125 USD."),
    ("id", "Pukul 12:30, 37 kg harganya Rp125.000."),
    ("hi", "12:30 बजे 37 किलो की कीमत 125 रुपये है।"),
    ("bn", "12:30 টায় 37 কিলোর দাম 125 টাকা।"),
    ("te", "12:30 కు 37 కిలోల ధర 125 రూపాయలు."),
    ("mr", "12:30 वाजता 37 किलोची किंमत 125 रुपये."),
    ("ur", "12:30 بجے 37 کلو کی قیمت 125 روپے ہے۔"),
];

const RUNS: usize = 101;
const WARMUP: usize = 200;

fn main() {
    println!(
        "{:<6} {:>6} {:>12} {:>14} {:>10} {:>10}",
        "lang", "chars", "median µs", "µs/100 chars", "allocs", "hit allocs"
    );
    let tn = zyphra_textnorm::Normalizer::new();
    for &(lang, text) in CASES {
        if !zyphra_textnorm::supported(lang) {
            continue;
        }
        for _ in 0..WARMUP {
            tn.clear_memo();
            black_box(tn.normalize(black_box(text), black_box(lang)));
        }
    }
    for &(lang, text) in CASES {
        if !zyphra_textnorm::supported(lang) {
            continue;
        }
        let mut times = Vec::with_capacity(RUNS);
        let mut allocs = Vec::with_capacity(RUNS);
        for _ in 0..RUNS {
            tn.clear_memo();
            let input = text.to_string();
            let a0 = ALLOCS.load(Ordering::Relaxed);
            let t0 = Instant::now();
            let out = tn.normalize(black_box(&input), black_box(lang));
            let dt = t0.elapsed();
            let a1 = ALLOCS.load(Ordering::Relaxed);
            black_box(out);
            times.push(dt.as_secs_f64() * 1e6);
            allocs.push(a1 - a0);
        }
        let hit_input = text.to_string();
        let a0 = ALLOCS.load(Ordering::Relaxed);
        black_box(tn.normalize(black_box(&hit_input), black_box(lang)));
        let hit_allocs = ALLOCS.load(Ordering::Relaxed) - a0;
        times.sort_by(|a, b| a.total_cmp(b));
        allocs.sort_unstable();
        let chars = text.chars().count();
        let median = times[times.len() / 2];
        println!(
            "{lang:<6} {chars:>6} {median:>12.1} {:>14.1} {:>10} {:>10}",
            median * 100.0 / chars as f64,
            allocs[allocs.len() / 2],
            hit_allocs
        );
    }
}
