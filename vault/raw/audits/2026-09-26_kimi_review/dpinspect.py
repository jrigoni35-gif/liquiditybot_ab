import duckdb, sys
con = duckdb.connect(sys.argv[1] + "/dp_copy.duckdb", read_only=True)
q = lambda s: print(con.execute(s).fetchall())
q("select count(*), cast(max(period_end) as varchar), cast(max(published_date) as varchar), cast(max(ingested_at) as varchar), min(data_age_days), max(data_age_days) from ats_venue_weekly")
q("select cast(period_start as varchar), is_complete, count(*), min(data_age_days), max(data_age_days) from ats_venue_weekly group by 1,2 order by 1")
q("select symbol, cast(max(period_end) as varchar), count(distinct period_start) from ats_venue_weekly where is_complete and symbol in ('COIN','MSTR','QQQ') group by 1")
