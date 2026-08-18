// diode/lb_diode.cpp — the first compiled referee (offline, SAFE class).
//
// DIODE LAW: reads ground truth (an outputs/ tree), publishes findings on
// stdout, feeds NOTHING back into any decision path. Never wired into the
// engine, never a DoD gate, never imported by the decision pipeline.
//
// Mirrors the PRE-REGISTERED rules of scripts/cohort_eval.py — era4_trips()
// and wilson() — rule-for-rule; tests/test_cpp_diode.py is a differential
// harness that runs the Python on the same fixture and pins agreement at
// 1e-9. The constants below are pre-registered: changing them after seeing
// data is exactly what pre-registration exists to prevent.
//
// v1 EXCLUSIONS (out of scope, not passed — a referee that silently
// approximates is worse than none):
//   - audit hash-chain verification: canonicalization depends on Python
//     float repr; the report carries "chain": "out-of-scope-v1".
//   - exact-decimal ledger x marks accounting identity (needs fills x
//     marks joins; equity figures here are double, harness-toleranced).
//
// CLI: lb_diode <outputs_dir>. ONE JSON object to stdout (ASCII only,
// numbers %.17g exact round-trip), exit 0 on success, 2 on unreadable outputs dir.
// Strict-ingest law: every malformed row is COUNTED, never coerced.
//
// Build: g++ -std=c++17 -O2 -Wall -Wextra -Werror -o lb_diode lb_diode.cpp
// (single translation unit, standard library only; no POSIX APIs, files
// opened in binary mode with \r handled, so MSVC builds it unchanged).

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

// --- pre-registered constants, verbatim from scripts/cohort_eval.py ------
static const double B4_TS = 1786359815.0;            // 2026-08-10T11:03:35Z (aeeaae36)
static const double CAPITAL_EPOCH_TS = 1786403127.0; // 2026-08-10T23:05:27Z
static const long long ERA4_MIN_N = 50;

// ---------------------------------------------------------------------------
// Shared low-level: Python-compatible float()/strip() over CSV cell text.
// ---------------------------------------------------------------------------

static bool is_pyws(char c) {
    // ASCII subset of Python str.strip()'s default whitespace. The ledgers
    // are ASCII; non-ASCII unicode whitespace is out of scope.
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' ||
           c == '\f';
}

static std::string py_strip(const std::string& s) {
    size_t b = 0, e = s.size();
    while (b < e && is_pyws(s[b])) ++b;
    while (e > b && is_pyws(s[e - 1])) --e;
    return s.substr(b, e - b);
}

// Mirrors Python float(str): strips whitespace, rejects empty and hex
// literals, requires full consumption, accepts inf/nan spellings (both
// languages do). Known non-mirrored corner: Python permits digit-group
// underscores ("1_0"); no ledger writer emits them.
static std::optional<double> py_float(const std::string& raw) {
    std::string t = py_strip(raw);
    if (t.empty()) return std::nullopt;
    size_t p = (t[0] == '+' || t[0] == '-') ? 1u : 0u;
    if (t.size() >= p + 2 && t[p] == '0' && (t[p + 1] == 'x' || t[p + 1] == 'X'))
        return std::nullopt;                 // Python float() rejects hex
    const char* cs = t.c_str();
    char* endp = nullptr;
    errno = 0;
    double v = std::strtod(cs, &endp);
    if (endp != cs + t.size()) return std::nullopt;
    return v;   // ERANGE overflow -> +-inf, matching Python float("1e999")
}

// ---------------------------------------------------------------------------
// S0. Strict CSV reader — header-indexed; a row whose field count differs
// from the header is dropped AND counted, never coerced. RFC-4180 quoting
// (embedded commas/quotes/newlines); CRLF tolerated; blank lines skipped
// (csv.DictReader skips them too, so drop counts stay comparable).
// ---------------------------------------------------------------------------

struct Csv {
    bool present = false;
    std::vector<std::string> header;
    std::vector<std::vector<std::string>> rows;   // width == header only
    long long dropped_short = 0, dropped_long = 0;
    // name -> LAST index: csv.DictReader lets a duplicated column name
    // resolve to the rightmost occurrence (the ml.history "side" lesson).
    std::unordered_map<std::string, size_t> idx;
};

static bool read_file(const std::string& path, std::string& out) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;
    std::ostringstream ss;
    ss << f.rdbuf();
    out = ss.str();
    return true;
}

static std::vector<std::vector<std::string>> csv_records(const std::string& s) {
    std::vector<std::vector<std::string>> recs;
    std::vector<std::string> cur;
    std::string field;
    bool in_quotes = false;
    bool rec_has_content = false;   // distinguishes a blank line from '""'
    const size_t n = s.size();
    size_t i = 0;
    auto end_record = [&]() {
        cur.push_back(field);
        field.clear();
        if (rec_has_content) recs.push_back(cur);
        cur.clear();
        rec_has_content = false;
    };
    while (i < n) {
        char c = s[i];
        if (in_quotes) {
            if (c == '"') {
                if (i + 1 < n && s[i + 1] == '"') { field += '"'; i += 2; }
                else { in_quotes = false; ++i; }
            } else { field += c; ++i; }
            continue;
        }
        if (c == '"' && field.empty()) { in_quotes = true; rec_has_content = true; ++i; }
        else if (c == '"') { field += '"'; ++i; }   // stray quote: literal
        else if (c == ',') { cur.push_back(field); field.clear(); rec_has_content = true; ++i; }
        else if (c == '\r' && i + 1 < n && s[i + 1] == '\n') { end_record(); i += 2; }
        else if (c == '\n') { end_record(); ++i; }
        else { field += c; rec_has_content = true; ++i; }
    }
    if (rec_has_content || !cur.empty() || !field.empty()) end_record();
    return recs;
}

static Csv load_csv(const std::filesystem::path& path) {
    Csv out;
    std::string raw;
    if (!read_file(path.string(), raw)) return out;
    out.present = true;
    auto recs = csv_records(raw);
    if (recs.empty()) return out;
    out.header = recs[0];
    for (size_t k = 0; k < out.header.size(); ++k) out.idx[out.header[k]] = k;
    const size_t width = out.header.size();
    for (size_t k = 1; k < recs.size(); ++k) {
        if (recs[k].size() < width) ++out.dropped_short;
        else if (recs[k].size() > width) ++out.dropped_long;
        else out.rows.push_back(std::move(recs[k]));
    }
    return out;
}

// Column absent from the header behaves like Python's r.get(name) -> None.
static const std::string* cell(const Csv& c, const std::vector<std::string>& row,
                               const char* name) {
    auto it = c.idx.find(name);
    if (it == c.idx.end()) return nullptr;
    return &row[it->second];
}

static std::optional<double> fnum(const Csv& c, const std::vector<std::string>& row,
                                  const char* name) {
    const std::string* v = cell(c, row, name);
    if (!v) return std::nullopt;
    return py_float(*v);
}

// ---------------------------------------------------------------------------
// S1. Minimal-but-correct JSON parser (recursive descent). Used for
// audit.jsonl; a line that fails to parse is COUNTED, never skipped
// silently. Depth-capped so hostile nesting cannot crash the referee.
// ---------------------------------------------------------------------------

struct JVal {
    enum Kind { Null, Bool, Num, Str, Obj, Arr } kind = Null;
    bool b = false;
    double num = 0.0;
    std::string str;
    std::vector<std::pair<std::string, JVal>> obj;
    std::vector<JVal> arr;
};

class JsonParser {
public:
    static bool parse(const std::string& s, JVal& out) {
        JsonParser p(s);
        p.ws();
        if (!p.value(out, 0)) return false;
        p.ws();
        return p.i_ == s.size();
    }

private:
    explicit JsonParser(const std::string& s) : s_(s) {}
    const std::string& s_;
    size_t i_ = 0;
    static const int MAX_DEPTH = 256;

    void ws() {
        while (i_ < s_.size() && (s_[i_] == ' ' || s_[i_] == '\t' ||
                                  s_[i_] == '\n' || s_[i_] == '\r')) ++i_;
    }
    bool lit(const char* w, size_t len) {
        if (s_.compare(i_, len, w) != 0) return false;
        i_ += len;
        return true;
    }
    static void utf8(std::string& out, unsigned cp) {
        if (cp < 0x80) out += static_cast<char>(cp);
        else if (cp < 0x800) {
            out += static_cast<char>(0xC0 | (cp >> 6));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        } else if (cp < 0x10000) {
            out += static_cast<char>(0xE0 | (cp >> 12));
            out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        } else {
            out += static_cast<char>(0xF0 | (cp >> 18));
            out += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
            out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        }
    }
    bool hex4(unsigned& out) {
        if (i_ + 4 > s_.size()) return false;
        out = 0;
        for (int k = 0; k < 4; ++k) {
            char c = s_[i_ + static_cast<size_t>(k)];
            unsigned d;
            if (c >= '0' && c <= '9') d = static_cast<unsigned>(c - '0');
            else if (c >= 'a' && c <= 'f') d = static_cast<unsigned>(c - 'a' + 10);
            else if (c >= 'A' && c <= 'F') d = static_cast<unsigned>(c - 'A' + 10);
            else return false;
            out = out * 16 + d;
        }
        i_ += 4;
        return true;
    }
    bool string(std::string& out) {
        if (i_ >= s_.size() || s_[i_] != '"') return false;
        ++i_;
        out.clear();
        while (i_ < s_.size()) {
            char c = s_[i_];
            if (c == '"') { ++i_; return true; }
            if (c == '\\') {
                ++i_;
                if (i_ >= s_.size()) return false;
                char e = s_[i_++];
                switch (e) {
                    case '"': out += '"'; break;
                    case '\\': out += '\\'; break;
                    case '/': out += '/'; break;
                    case 'b': out += '\b'; break;
                    case 'f': out += '\f'; break;
                    case 'n': out += '\n'; break;
                    case 'r': out += '\r'; break;
                    case 't': out += '\t'; break;
                    case 'u': {
                        unsigned cp;
                        if (!hex4(cp)) return false;
                        if (cp >= 0xD800 && cp <= 0xDBFF && i_ + 1 < s_.size() &&
                            s_[i_] == '\\' && s_[i_ + 1] == 'u') {
                            size_t save = i_;
                            i_ += 2;
                            unsigned lo;
                            if (hex4(lo) && lo >= 0xDC00 && lo <= 0xDFFF)
                                cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                            else { i_ = save; cp = 0xFFFD; }
                        } else if (cp >= 0xD800 && cp <= 0xDFFF) {
                            cp = 0xFFFD;   // lone surrogate: replaced, not fatal
                        }
                        utf8(out, cp);
                        break;
                    }
                    default: return false;
                }
            } else if (static_cast<unsigned char>(c) < 0x20) {
                return false;              // raw control char is invalid JSON
            } else { out += c; ++i_; }
        }
        return false;
    }
    bool number(JVal& out) {
        size_t start = i_;
        while (i_ < s_.size()) {
            char c = s_[i_];
            if ((c >= '0' && c <= '9') || c == '+' || c == '-' || c == '.' ||
                c == 'e' || c == 'E') ++i_;
            else break;
        }
        std::string t = s_.substr(start, i_ - start);
        const char* cs = t.c_str();
        char* endp = nullptr;
        errno = 0;
        double v = std::strtod(cs, &endp);
        if (endp != cs + t.size() || t.empty()) return false;
        out.kind = JVal::Num;
        out.num = v;
        return true;
    }
    bool value(JVal& out, int depth) {
        if (depth > MAX_DEPTH || i_ >= s_.size()) return false;
        char c = s_[i_];
        if (c == '{') {
            ++i_;
            out.kind = JVal::Obj;
            ws();
            if (i_ < s_.size() && s_[i_] == '}') { ++i_; return true; }
            while (true) {
                ws();
                std::string key;
                if (!string(key)) return false;
                ws();
                if (i_ >= s_.size() || s_[i_] != ':') return false;
                ++i_;
                ws();
                JVal v;
                if (!value(v, depth + 1)) return false;
                out.obj.emplace_back(std::move(key), std::move(v));
                ws();
                if (i_ >= s_.size()) return false;
                if (s_[i_] == ',') { ++i_; continue; }
                if (s_[i_] == '}') { ++i_; return true; }
                return false;
            }
        }
        if (c == '[') {
            ++i_;
            out.kind = JVal::Arr;
            ws();
            if (i_ < s_.size() && s_[i_] == ']') { ++i_; return true; }
            while (true) {
                ws();
                JVal v;
                if (!value(v, depth + 1)) return false;
                out.arr.push_back(std::move(v));
                ws();
                if (i_ >= s_.size()) return false;
                if (s_[i_] == ',') { ++i_; continue; }
                if (s_[i_] == ']') { ++i_; return true; }
                return false;
            }
        }
        if (c == '"') { out.kind = JVal::Str; return string(out.str); }
        if (c == 't') { out.kind = JVal::Bool; out.b = true; return lit("true", 4); }
        if (c == 'f') { out.kind = JVal::Bool; out.b = false; return lit("false", 5); }
        if (c == 'n') { out.kind = JVal::Null; return lit("null", 4); }
        if (c == '-' || (c >= '0' && c <= '9')) return number(out);
        return false;
    }
};

// Duplicate keys resolve to the LAST occurrence, like Python dict literals.
static const JVal* jget(const JVal& obj, const char* key) {
    if (obj.kind != JVal::Obj) return nullptr;
    const JVal* found = nullptr;
    for (const auto& kv : obj.obj)
        if (kv.first == key) found = &kv.second;
    return found;
}

// ---------------------------------------------------------------------------
// S2. Ledger scan — equity.csv (ts,equity,...). start/end/min/max over
// VALID rows (ts AND equity both parse); invalid rows stay counted in the
// row total, never coerced. Doubles only — the exact-decimal accounting
// identity is a v1 exclusion.
// ---------------------------------------------------------------------------

struct EquityStats {
    long long rows = 0, valid = 0;
    double start = 0, end = 0, mn = 0, mx = 0;
};

static EquityStats scan_equity(const Csv& c) {
    EquityStats st;
    st.rows = static_cast<long long>(c.rows.size());
    for (const auto& row : c.rows) {
        auto ts = fnum(c, row, "ts");
        auto eq = fnum(c, row, "equity");
        if (!ts || !eq) continue;
        if (st.valid == 0) { st.start = *eq; st.mn = *eq; st.mx = *eq; }
        st.end = *eq;
        st.mn = std::min(st.mn, *eq);
        st.mx = std::max(st.mx, *eq);
        ++st.valid;
    }
    return st;
}

// ---------------------------------------------------------------------------
// S3. Era-4 trip reconstruction — fills.csv. Rule-for-rule mirror of
// scripts/cohort_eval.era4_trips (include_hedges=False, since=None ->
// cut = max(B4_TS, CAPITAL_EPOCH_TS)). Order of checks is load-bearing:
// the duplicate-signature set consumes a signature BEFORE the entry-only
// and epoch filters run, exactly as the Python does.
// ---------------------------------------------------------------------------

struct Trip {
    std::string pid;
    double t = 0;                       // tclose
    std::optional<double> t_open;
    double gross_pct = 0, net_pct = 0;
    std::vector<std::string> eras;      // sorted, like Python sorted(eras)
    long long stale_legs = 0, prestamp_legs = 0;
};

// round(v, 6)/round(v, 4) stand-in for the duplicate signature. llround is
// half-away-from-zero where Python's round is banker's; the values a ledger
// carries are far from the tie cases and the differential harness pins
// agreement. Guarded against the llround domain edge; out-of-range or nan
// falls back to the exact bit pattern (%.17g), which is what Python's
// round() equality degenerates to at that magnitude anyway.
static std::string rkey(double v, double scale) {
    double s = v * scale;
    if (!(std::fabs(s) < 9.0e18)) {
        char b[40];
        std::snprintf(b, sizeof b, "%.17g", v);
        return b;
    }
    return std::to_string(std::llround(s));
}

static std::vector<Trip> era4_trips(const Csv& fills) {
    std::vector<Trip> out;
    if (!fills.present) return out;
    // group by position_id in FIRST-APPEARANCE order (Python dict order);
    // empty pid is skipped from grouping (falsy under `if r.get(...)`)
    std::vector<std::string> pid_order;
    std::unordered_map<std::string, std::vector<size_t>> by_pid;
    for (size_t k = 0; k < fills.rows.size(); ++k) {
        const std::string* pid = cell(fills, fills.rows[k], "position_id");
        if (!pid || pid->empty()) continue;
        auto it = by_pid.find(*pid);
        if (it == by_pid.end()) {
            pid_order.push_back(*pid);
            by_pid[*pid].push_back(k);
        } else {
            it->second.push_back(k);
        }
    }
    std::set<std::string> seen;
    const double cut = std::max(B4_TS, CAPITAL_EPOCH_TS);
    for (const auto& pid : pid_order) {
        const auto& legs = by_pid[pid];
        // Python: legs.sort(key=lambda r: _f(r, "ts") or 0.0) — a STABLE
        // sort with unparseable ts keyed as 0.0. A nan key would break the
        // C++ strict-weak-ordering contract, so it is keyed 0.0 as well
        // (Python's order under nan keys is arbitrary timsort residue —
        // no ledger writes ts="nan").
        std::vector<std::pair<double, size_t>> keyed;
        keyed.reserve(legs.size());
        for (size_t idx : legs) {
            auto k = fnum(fills, fills.rows[idx], "ts");
            double kv = (k && !std::isnan(*k)) ? *k : 0.0;
            keyed.emplace_back(kv, idx);
        }
        std::stable_sort(keyed.begin(), keyed.end(),
                         [](const std::pair<double, size_t>& a,
                            const std::pair<double, size_t>& b) {
                             return a.first < b.first;
                         });
        double cash = 0, fees = 0, esz = 0, xsz = 0, enot = 0;
        std::optional<double> tclose, topen;
        std::string opened_by;
        bool has_opened = false, ok = true;
        std::set<std::string> eras;
        long long stale = 0, prestamp = 0;
        std::string sig;
        for (const auto& kp : keyed) {
            const auto& row = fills.rows[kp.second];
            auto sz = fnum(fills, row, "fill_size");
            auto px = fnum(fills, row, "fill_price");
            auto fee = fnum(fills, row, "fees_delta_usd");
            if (!sz || !px || !fee || *sz <= 0 || *px <= 0) { ok = false; break; }
            const std::string* era = cell(fills, row, "exec_era");
            if (!era) ++stale;                       // absent column: stale binary
            else {
                std::string e = py_strip(*era);
                if (e.empty()) ++prestamp;           // blank: pre-stamp row
                else eras.insert(e);
            }
            const std::string* side = cell(fills, row, "side");
            const bool sell = side && *side == "sell";
            cash += sell ? (*sz * *px) : -(*sz * *px);
            fees += *fee;
            const std::string* pr = cell(fills, row, "purpose");
            const std::string purpose = pr ? *pr : "";
            if (purpose == "entry" || purpose == "hedge") {
                esz += *sz;
                enot += *sz * *px;
                if (!has_opened) {
                    has_opened = true;
                    opened_by = purpose;
                    topen = fnum(fills, row, "ts");
                }
            } else if (purpose == "exit") {
                xsz += *sz;
                tclose = fnum(fills, row, "ts");     // None-overwrite mirrored
            }
            sig += purpose; sig += '\x1f';
            sig += side ? *side : ""; sig += '\x1f';
            sig += rkey(*sz, 1e6); sig += '\x1f';
            sig += rkey(*px, 1e4); sig += '\x1e';
        }
        if (!ok || esz <= 0 || xsz <= 0 || enot <= 0 || !tclose) continue;
        if (std::fabs(xsz - esz) / esz > 0.02) continue;
        if (!seen.insert(sig).second) continue;      // duplicate pattern dropped
        if (opened_by != "entry") continue;          // hedges are insurance
        if (*tclose < cut) continue;                 // honest fills, one regime
        Trip t;
        t.pid = pid;
        t.t = *tclose;
        t.t_open = topen;
        t.gross_pct = 100.0 * cash / enot;
        t.net_pct = 100.0 * (cash - fees) / enot;
        t.eras.assign(eras.begin(), eras.end());     // std::set is sorted
        t.stale_legs = stale;
        t.prestamp_legs = prestamp;
        out.push_back(std::move(t));
    }
    return out;
}

// ---------------------------------------------------------------------------
// S4. Corpus scan — signal_history.csv: rows by source, label counts
// (label=="1" wins over labeled rows), base rate, Wilson mirroring
// cohort_eval.wilson exactly (n==0 -> (0,0,0)).
// ---------------------------------------------------------------------------

struct LabelStats {
    long long rows = 0, labeled = 0, wins = 0;
    std::map<std::string, long long> by_source;
    double wilson[3] = {0.0, 0.0, 0.0};
};

static void wilson(long long k, long long n, double z, double out[3]) {
    if (n == 0) { out[0] = out[1] = out[2] = 0.0; return; }
    double p = static_cast<double>(k) / static_cast<double>(n);
    double d = 1.0 + z * z / static_cast<double>(n);
    double c = (p + z * z / (2.0 * static_cast<double>(n))) / d;
    double h = z * std::sqrt(p * (1 - p) / static_cast<double>(n) +
                             z * z / (4.0 * static_cast<double>(n) *
                                      static_cast<double>(n))) / d;
    out[0] = p;
    out[1] = std::max(0.0, c - h);
    out[2] = std::min(1.0, c + h);
}

static LabelStats scan_signal(const Csv& c) {
    LabelStats st;
    st.rows = static_cast<long long>(c.rows.size());
    for (const auto& row : c.rows) {
        const std::string* src = cell(c, row, "source");
        std::string s = src ? py_strip(*src) : "";
        if (s.empty()) s = "<blank>";
        ++st.by_source[s];
        const std::string* lab = cell(c, row, "label");
        if (!lab) continue;
        std::string l = py_strip(*lab);
        if (l.empty()) continue;
        ++st.labeled;
        if (l == "1") ++st.wins;
    }
    wilson(st.wins, st.labeled, 1.96, st.wilson);
    return st;
}

// ---------------------------------------------------------------------------
// S5. Audit counts — audit.jsonl: records, bad_lines, count by code
// (top 12, count-desc then code-asc for determinism), min/max ts.
// NO chain verification in v1 (canonicalization depends on Python float
// repr); the report says "out-of-scope-v1" so absence never reads as a pass.
// ---------------------------------------------------------------------------

struct AuditStats {
    bool present = false;
    long long records = 0, bad_lines = 0;
    std::map<std::string, long long> codes;
    bool has_ts = false;
    double ts_min = 0, ts_max = 0;
};

static AuditStats scan_audit(const std::filesystem::path& path) {
    AuditStats st;
    std::string raw;
    if (!read_file(path.string(), raw)) return st;
    st.present = true;
    size_t pos = 0;
    while (pos <= raw.size()) {
        size_t nl = raw.find('\n', pos);
        std::string line = raw.substr(pos, nl == std::string::npos
                                               ? std::string::npos : nl - pos);
        pos = (nl == std::string::npos) ? raw.size() + 1 : nl + 1;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (py_strip(line).empty()) continue;        // blank lines are not bad
        JVal v;
        if (!JsonParser::parse(line, v)) { ++st.bad_lines; continue; }
        ++st.records;
        const JVal* code = jget(v, "code");
        if (code && code->kind == JVal::Str) ++st.codes[code->str];
        const JVal* ts = jget(v, "ts");
        if (ts && ts->kind == JVal::Num) {
            if (!st.has_ts) { st.ts_min = st.ts_max = ts->num; st.has_ts = true; }
            st.ts_min = std::min(st.ts_min, ts->num);
            st.ts_max = std::max(st.ts_max, ts->num);
        }
    }
    return st;
}

// ---------------------------------------------------------------------------
// S6. Report — one JSON object, ASCII only. Numbers print %.17g: the
// shortest-exact %.10g quantized ~5e-10 RELATIVE, which misses the
// harness's 1e-9 ABSOLUTE tolerance once |value| >= 10 (review finding,
// 2026-08-19 — fuzz tripped it at gross ~100%); %.17g round-trips every
// double exactly, so the tolerance stays absolute and honest.
// ---------------------------------------------------------------------------

static std::string jnum(double v) {
    if (std::isnan(v)) return "null";                // no NaN in JSON
    if (std::isinf(v)) return v > 0 ? "1e999" : "-1e999";
    char buf[64];
    std::snprintf(buf, sizeof buf, "%.17g", v);
    return buf;
}

static std::string jint(long long v) { return std::to_string(v); }

// ASCII-only string emitter: control bytes and non-ASCII become \uXXXX
// (UTF-8 decoded; malformed bytes become U+FFFD, never a crash).
static void jstr(std::string& o, const std::string& s) {
    o += '"';
    size_t i = 0;
    const size_t n = s.size();
    auto esc = [&o](unsigned cp) {
        char b[8];
        if (cp >= 0x10000) {
            unsigned v = cp - 0x10000;
            std::snprintf(b, sizeof b, "\\u%04x", 0xD800 + (v >> 10));
            o += b;
            std::snprintf(b, sizeof b, "\\u%04x", 0xDC00 + (v & 0x3FF));
            o += b;
        } else {
            std::snprintf(b, sizeof b, "\\u%04x", cp);
            o += b;
        }
    };
    while (i < n) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        if (c == '"') { o += "\\\""; ++i; }
        else if (c == '\\') { o += "\\\\"; ++i; }
        else if (c == '\b') { o += "\\b"; ++i; }
        else if (c == '\f') { o += "\\f"; ++i; }
        else if (c == '\n') { o += "\\n"; ++i; }
        else if (c == '\r') { o += "\\r"; ++i; }
        else if (c == '\t') { o += "\\t"; ++i; }
        else if (c < 0x20) { esc(c); ++i; }
        else if (c < 0x80) { o += static_cast<char>(c); ++i; }
        else {
            unsigned cp = 0xFFFD;
            size_t len = 1;
            if ((c & 0xE0) == 0xC0 && i + 1 < n &&
                (static_cast<unsigned char>(s[i + 1]) & 0xC0) == 0x80) {
                cp = (static_cast<unsigned>(c & 0x1F) << 6) |
                     (static_cast<unsigned char>(s[i + 1]) & 0x3Fu);
                len = 2;
            } else if ((c & 0xF0) == 0xE0 && i + 2 < n &&
                       (static_cast<unsigned char>(s[i + 1]) & 0xC0) == 0x80 &&
                       (static_cast<unsigned char>(s[i + 2]) & 0xC0) == 0x80) {
                cp = (static_cast<unsigned>(c & 0x0F) << 12) |
                     ((static_cast<unsigned char>(s[i + 1]) & 0x3Fu) << 6) |
                     (static_cast<unsigned char>(s[i + 2]) & 0x3Fu);
                len = 3;
            } else if ((c & 0xF8) == 0xF0 && i + 3 < n &&
                       (static_cast<unsigned char>(s[i + 1]) & 0xC0) == 0x80 &&
                       (static_cast<unsigned char>(s[i + 2]) & 0xC0) == 0x80 &&
                       (static_cast<unsigned char>(s[i + 3]) & 0xC0) == 0x80) {
                cp = (static_cast<unsigned>(c & 0x07) << 18) |
                     ((static_cast<unsigned char>(s[i + 1]) & 0x3Fu) << 12) |
                     ((static_cast<unsigned char>(s[i + 2]) & 0x3Fu) << 6) |
                     (static_cast<unsigned char>(s[i + 3]) & 0x3Fu);
                len = 4;
            }
            esc(cp);
            i += len;
        }
    }
    o += '"';
}

static void emit_ingest_csv(std::string& o, const char* name, const Csv& c) {
    o += "\"";
    o += name;
    o += "\": {\"present\": ";
    o += c.present ? "true" : "false";
    o += ", \"rows\": " + jint(static_cast<long long>(c.rows.size()));
    o += ", \"dropped_short\": " + jint(c.dropped_short);
    o += ", \"dropped_long\": " + jint(c.dropped_long);
    o += "}";
    o += ", ";      // every section is followed by another (audit closes the group)
}

int main(int argc, char** argv) {
    if (argc != 2) {
        std::fprintf(stderr, "usage: lb_diode <outputs_dir>\n");
        return 2;
    }
    const std::filesystem::path outdir(argv[1]);
    std::error_code ec;
    if (!std::filesystem::is_directory(outdir, ec) || ec) {
        std::fprintf(stderr, "lb_diode: unreadable outputs dir: %s\n", argv[1]);
        return 2;
    }

    const Csv equity_csv = load_csv(outdir / "equity.csv");
    const Csv fills_csv = load_csv(outdir / "fills.csv");
    const Csv signal_csv = load_csv(outdir / "signal_history.csv");
    const AuditStats audit = scan_audit(outdir / "audit.jsonl");

    const EquityStats eq = scan_equity(equity_csv);
    const std::vector<Trip> trips = era4_trips(fills_csv);
    const LabelStats labels = scan_signal(signal_csv);

    std::string o;
    o.reserve(1 << 16);
    o += "{\"diode\": \"cpp\", \"version\": 1, \"outputs_dir\": ";
    jstr(o, outdir.string());
    o += ", \"ingest\": {";
    emit_ingest_csv(o, "equity", equity_csv);
    emit_ingest_csv(o, "fills", fills_csv);
    emit_ingest_csv(o, "signal", signal_csv);
    o += "\"audit\": {\"present\": ";
    o += audit.present ? "true" : "false";
    o += ", \"records\": " + jint(audit.records);
    o += ", \"bad_lines\": " + jint(audit.bad_lines);
    if (audit.has_ts) {
        o += ", \"ts_min\": " + jnum(audit.ts_min);
        o += ", \"ts_max\": " + jnum(audit.ts_max);
    }
    o += "}}";

    // S2 report
    o += ", \"equity\": {\"rows\": " + jint(eq.rows);
    o += ", \"valid\": " + jint(eq.valid);
    if (eq.valid > 0) {
        o += ", \"start\": " + jnum(eq.start);
        o += ", \"end\": " + jnum(eq.end);
        o += ", \"min\": " + jnum(eq.mn);
        o += ", \"max\": " + jnum(eq.mx);
    }
    o += "}";

    // S3 report — summary mirrors era4_section arithmetic (sum over the
    // SORTED values, median = sorted[n // 2]) so the harness can diff it
    // against the Python term-for-term.
    {
        const long long n = static_cast<long long>(trips.size());
        o += ", \"era4\": {\"accrual_n\": " + jint(n);
        o += ", \"target\": " + jint(ERA4_MIN_N);
        if (n > 0) {
            std::vector<double> g, nt;
            g.reserve(trips.size());
            nt.reserve(trips.size());
            double tmin = trips[0].t, tmax = trips[0].t;
            for (const auto& t : trips) {
                g.push_back(t.gross_pct);
                nt.push_back(t.net_pct);
                tmin = std::min(tmin, t.t);
                tmax = std::max(tmax, t.t);
            }
            std::sort(g.begin(), g.end());
            std::sort(nt.begin(), nt.end());
            double gs = 0, ns = 0;
            long long npos = 0;
            for (double v : g) { gs += v; if (v > 0) ++npos; }
            for (double v : nt) ns += v;
            o += ", \"gross_mean_pct\": " + jnum(gs / static_cast<double>(n));
            o += ", \"gross_median_pct\": " + jnum(g[static_cast<size_t>(n / 2)]);
            o += ", \"net_mean_pct\": " + jnum(ns / static_cast<double>(n));
            o += ", \"net_median_pct\": " + jnum(nt[static_cast<size_t>(n / 2)]);
            o += ", \"n_pos_gross\": " + jint(npos);
            o += ", \"tclose_min\": " + jnum(tmin);
            o += ", \"tclose_max\": " + jnum(tmax);
        }
        o += ", \"trips\": [";
        for (size_t k = 0; k < trips.size(); ++k) {
            const Trip& t = trips[k];
            if (k) o += ", ";
            o += "{\"pid\": ";
            jstr(o, t.pid);
            o += ", \"t\": " + jnum(t.t);
            o += ", \"t_open\": ";
            o += t.t_open ? jnum(*t.t_open) : "null";
            o += ", \"gross_pct\": " + jnum(t.gross_pct);
            o += ", \"net_pct\": " + jnum(t.net_pct);
            o += ", \"eras\": [";
            for (size_t e = 0; e < t.eras.size(); ++e) {
                if (e) o += ", ";
                jstr(o, t.eras[e]);
            }
            o += "], \"stale_legs\": " + jint(t.stale_legs);
            o += ", \"prestamp_legs\": " + jint(t.prestamp_legs);
            o += "}";
        }
        o += "]}";
    }

    // S4 report
    o += ", \"labels\": {\"rows\": " + jint(labels.rows);
    o += ", \"by_source\": {";
    {
        bool first = true;
        for (const auto& kv : labels.by_source) {
            if (!first) o += ", ";
            first = false;
            jstr(o, kv.first);
            o += ": " + jint(kv.second);
        }
    }
    o += "}, \"labeled\": " + jint(labels.labeled);
    o += ", \"wins\": " + jint(labels.wins);
    o += ", \"base_rate\": " + jnum(labels.labeled
                                        ? static_cast<double>(labels.wins) /
                                              static_cast<double>(labels.labeled)
                                        : 0.0);
    o += ", \"wilson\": [" + jnum(labels.wilson[0]) + ", " +
         jnum(labels.wilson[1]) + ", " + jnum(labels.wilson[2]) + "]}";

    // S5 report — top 12 codes, count-desc then code-asc
    o += ", \"audit_codes\": {";
    {
        std::vector<std::pair<std::string, long long>> v(audit.codes.begin(),
                                                         audit.codes.end());
        std::sort(v.begin(), v.end(),
                  [](const std::pair<std::string, long long>& a,
                     const std::pair<std::string, long long>& b) {
                      if (a.second != b.second) return a.second > b.second;
                      return a.first < b.first;
                  });
        if (v.size() > 12) v.resize(12);
        for (size_t k = 0; k < v.size(); ++k) {
            if (k) o += ", ";
            jstr(o, v[k].first);
            o += ": " + jint(v[k].second);
        }
    }
    o += "}";

    o += ", \"chain\": \"out-of-scope-v1\"}";
    o += '\n';
    std::fwrite(o.data(), 1, o.size(), stdout);
    return 0;
}
