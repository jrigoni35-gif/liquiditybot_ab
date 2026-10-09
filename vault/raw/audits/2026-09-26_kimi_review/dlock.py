import duckdb, subprocess, sys, tempfile, os
PY=sys.executable
d=tempfile.mkdtemp(); db=os.path.join(d,"m.duckdb")
c=duckdb.connect(db); c.execute("create table ats_venue_weekly(a int)"); c.close()
w="import duckdb,sys\ntry:\n c=duckdb.connect(sys.argv[1]); c.execute('insert into ats_venue_weekly values (1)'); print('WRITER_OK')\nexcept Exception as e: print('WRITER_FAIL',type(e).__name__,str(e)[:160])\n"
print("control (no reader):", subprocess.run([PY,"-c",w,db],capture_output=True,text=True).stdout.strip())
r=duckdb.connect(db, read_only=True)   # bot-style long-lived reader
print("with RO reader held:", subprocess.run([PY,"-c",w,db],capture_output=True,text=True).stdout.strip())
r.close()
print("after reader closed:", subprocess.run([PY,"-c",w,db],capture_output=True,text=True).stdout.strip())
print("duckdb", duckdb.__version__)
