"""tests/test_config_guard_context.py — Compounder Phase B `context`
block coherence: the guard refuses configs where the context engine
would be structurally broken (Compounder spec §3, task-B3 brief)."""
from core.config_guard import validate


def _cfg(**ctx):
    base = {
        "context": {
            "enabled": True,
            "poll_hours": 6.0,
            "next_halving_date": "2028-04-17",
            "phase_bucket_days": {"accumulation": 180, "expansion": 540,
                                  "euphoria": 900, "contraction": 1460},
            "stress": {"dff_center": 0.0, "dff_scale": 0.5,
                      "t10y2y_center": 0.0, "t10y2y_scale": 0.5,
                      "vix_center": 20.0, "vix_scale": 10.0, "clip": 2.0},
            "flow": {"cot_scale": 5000.0, "stable_scale_pct": 2.0,
                    "clip": 2.0},
            "event_window": {"fomc_pre_h": 24.0, "fomc_post_h": 6.0,
                            "expiry_pre_h": 8.0, "expiry_post_h": 2.0},
            "urls": {
                "fred_dff": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF",
                "fred_t10y2y": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y",
                "fred_vix": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS",
                "cot_finfut": "https://www.cftc.gov/dea/newcot/FinFutWk.txt",
                "stablecoins": "https://stablecoins.llama.fi/stablecoins?includePrices=false",
            },
        },
    }
    base["context"].update(ctx)
    return base


def _fatals(cfg):
    return [m for s, m in validate(cfg) if s == "FATAL" and "context" in m]


def test_default_block_clean():
    assert _fatals(_cfg()) == []


def test_absent_block_clean():
    # module defaults apply; the guard only judges a present block
    assert _fatals({}) == []


def test_poll_hours_below_one_fatal():
    assert _fatals(_cfg(poll_hours=0.5))


def test_poll_hours_at_floor_clean():
    assert _fatals(_cfg(poll_hours=1.0)) == []


def test_missing_bucket_key_fatal():
    buckets = {"accumulation": 180, "expansion": 540, "euphoria": 900}
    assert _fatals(_cfg(phase_bucket_days=buckets))


def test_non_monotonic_buckets_fatal():
    buckets = {"accumulation": 180, "expansion": 100, "euphoria": 900,
              "contraction": 1460}
    assert _fatals(_cfg(phase_bucket_days=buckets))


def test_equal_bucket_bounds_fatal():
    buckets = {"accumulation": 180, "expansion": 180, "euphoria": 900,
              "contraction": 1460}
    assert _fatals(_cfg(phase_bucket_days=buckets))


def test_reordered_bucket_keys_fatal():
    # values stay strictly increasing when read in canonical order, but
    # insertion order is scrambled - data/context_engine.py's
    # phase_bucket() iterates dict INSERTION order (not this canonical
    # order), so this would silently mislabel every phase despite the
    # values themselves being monotonic.
    buckets = {"expansion": 540, "accumulation": 180, "euphoria": 900,
              "contraction": 1460}
    assert _fatals(_cfg(phase_bucket_days=buckets))


def test_canonical_bucket_order_clean():
    buckets = {"accumulation": 180, "expansion": 540, "euphoria": 900,
              "contraction": 1460}
    assert _fatals(_cfg(phase_bucket_days=buckets)) == []


def test_stress_zero_scale_fatal():
    stress = {"dff_center": 0.0, "dff_scale": 0.0, "t10y2y_center": 0.0,
              "t10y2y_scale": 0.5, "vix_center": 20.0, "vix_scale": 10.0,
              "clip": 2.0}
    assert _fatals(_cfg(stress=stress))


def test_stress_negative_clip_fatal():
    stress = {"dff_center": 0.0, "dff_scale": 0.5, "t10y2y_center": 0.0,
              "t10y2y_scale": 0.5, "vix_center": 20.0, "vix_scale": 10.0,
              "clip": -1.0}
    assert _fatals(_cfg(stress=stress))


def test_flow_zero_scale_fatal():
    flow = {"cot_scale": 0.0, "stable_scale_pct": 2.0, "clip": 2.0}
    assert _fatals(_cfg(flow=flow))


def test_flow_negative_clip_fatal():
    flow = {"cot_scale": 5000.0, "stable_scale_pct": 2.0, "clip": -2.0}
    assert _fatals(_cfg(flow=flow))


def test_event_window_negative_hours_fatal():
    ew = {"fomc_pre_h": -1.0, "fomc_post_h": 6.0, "expiry_pre_h": 8.0,
          "expiry_post_h": 2.0}
    assert _fatals(_cfg(event_window=ew))


def test_event_window_zero_hours_clean():
    ew = {"fomc_pre_h": 0.0, "fomc_post_h": 0.0, "expiry_pre_h": 0.0,
          "expiry_post_h": 0.0}
    assert _fatals(_cfg(event_window=ew)) == []


def test_http_url_fatal():
    urls = {"fred_dff": "http://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF",
            "fred_t10y2y": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y",
            "fred_vix": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS",
            "cot_finfut": "https://www.cftc.gov/dea/newcot/FinFutWk.txt",
            "stablecoins": "https://stablecoins.llama.fi/stablecoins?includePrices=false"}
    assert _fatals(_cfg(urls=urls))


def test_all_https_urls_clean():
    assert _fatals(_cfg()) == []
