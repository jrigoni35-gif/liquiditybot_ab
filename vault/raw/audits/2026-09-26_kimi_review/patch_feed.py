import sys
p = sys.argv[1] + "/data/darkpool_feed.py"
b = open(p, "rb").read()
crlf = b"\r\n" in b
s = b.decode("utf-8").replace("\r\n", "\n")
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)
rep("""        self._con = con            # injectable for tests
        self._db_ok = con is not None
""", """        self._con = con            # injectable for tests
        self._db_ok = con is not None
        # a connection WE opened is released after every poll: a lifetime
        # read-only handle blocks the external mirror writer on Windows
        # (so the mirror could never refresh while the bot runs), and a
        # handle DuckDB invalidated after an I/O error would otherwise be
        # retried forever with no reconnect. Injected (test) cons persist.
        self._owns_con = con is None
        self._opened_once = False
""")
rep("""            self._con = duckdb.connect(self.db_path, read_only=True)
            self._db_ok = True
            self._warned = False
            log.info(f"darkpool mirror opened read-only: {self.db_path}")
            return True""", """            self._con = duckdb.connect(self.db_path, read_only=True)
            self._db_ok = True
            self._warned = False
            if not self._opened_once:
                self._opened_once = True
                log.info(f"darkpool mirror opened read-only: {self.db_path}")
            return True""")
rep("""        self._snapshot.available = False
        self._snapshot.dp_frozen = False
        self._snapshot.is_complete = False
""", """        self._snapshot.available = False
        self._snapshot.dp_frozen = False
        self._snapshot.is_complete = False
        # numerics neutral too (the docstring's promise): a degraded
        # snapshot must not carry the last live values under available=False
        self._snapshot.dp_surge_z = 0.0
        self._snapshot.dp_vol_z = 0.0
        self._snapshot.dp_hhi = 0.0
""")
rep("""        try:
            self._snapshot = self._poll(now)
        except Exception as e:
            log.warning(f"darkpool poll failed ({e}) - keeping last snapshot")
            self._degrade()
        return self._snapshot""", """        try:
            self._snapshot = self._poll(now)
        except Exception as e:
            log.warning(f"darkpool poll failed ({e}) - snapshot degraded")
            self._degrade()
        finally:
            if self._owns_con:
                self.close()
        return self._snapshot""")
rep("""        age_days = max((v["data_age_days"] or 0) for v in per.values())
""", """        # data_age_days in the mirror is STAMPED AT INGEST and never grows;
        # staleness is measured here, against the poll clock
        newest_end = max(v["period_end"] for v in per.values())
        try:
            age_days = int((now - time.mktime(time.strptime(
                newest_end[:10], "%Y-%m-%d"))) // 86400)
        except (ValueError, OverflowError):
            age_days = max((v["data_age_days"] or 0) for v in per.values())
""")
out = s.replace("\n", "\r\n") if crlf else s
open(p, "wb").write(out.encode("utf-8"))
print("patched", p, "crlf", crlf)
