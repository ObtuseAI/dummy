# Wave-46d: one-shot ledger VACUUM maintenance.
#
# VACUUM rewrites the DB to reclaim freed pages (the daily prune frees ~half the
# file into the freelist) and defragment it -- but it needs EXCLUSIVE access, so
# this disables every Dummy* scheduled task, kills running instances, waits until
# nothing holds ledger.db, runs VACUUM, then ALWAYS re-enables the tasks
# (finally). Cycles pause for the VACUUM duration (~minutes). Rerunnable.
#
# The web dashboard (reads artifacts only, never the ledger) is left running.

$ErrorActionPreference = "Stop"
$ledger = "D:\DummyRuntime\autonomy\ledger.db"
$python = "C:\Python314\python.exe"

# Skip cheaply when there is little to reclaim -- a scheduled run must not pause
# the runtime unless the freelist is big enough to be worth the downtime.
$minFreeGiB = [double]$env:DUMMY_VACUUM_MIN_FREE_GIB
if ($minFreeGiB -le 0) { $minFreeGiB = 1.5 }
$freeGiB = [double](& $python -c "import sqlite3;c=sqlite3.connect(r'$ledger',timeout=30);f=c.execute('PRAGMA freelist_count').fetchone()[0];p=c.execute('PRAGMA page_size').fetchone()[0];c.close();print(f*p/1024**3)")
if ($freeGiB -lt $minFreeGiB) {
    Write-Host ("freelist {0:N2}GiB < {1:N2}GiB threshold -- skipping VACUUM (no runtime pause)" -f $freeGiB, $minFreeGiB)
    exit 0
}
Write-Host ("freelist {0:N2}GiB >= {1:N2}GiB threshold -- proceeding with VACUUM" -f $freeGiB, $minFreeGiB)

$rmSrc = @'
using System;using System.Collections.Generic;using System.Runtime.InteropServices;
public static class RMV{[DllImport("rstrtmgr.dll",CharSet=CharSet.Unicode)]static extern int RmStartSession(out uint h,int f,string k);[DllImport("rstrtmgr.dll")]static extern int RmEndSession(uint h);[DllImport("rstrtmgr.dll",CharSet=CharSet.Unicode)]static extern int RmRegisterResources(uint h,uint n,string[] f,uint na,IntPtr a,uint ns,string[] s);[StructLayout(LayoutKind.Sequential)]struct UP{public int PID;public System.Runtime.InteropServices.ComTypes.FILETIME t;}[StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)]struct PI{public UP Process;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=256)]public string n;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=64)]public string s;public uint at;public uint st;public uint ts;[MarshalAs(UnmanagedType.Bool)]public bool r;}[DllImport("rstrtmgr.dll")]static extern int RmGetList(uint h,out uint need,ref uint got,[In,Out]PI[] a,ref uint reb);public static List<int> H(string p){var r=new List<int>();uint h;if(RmStartSession(out h,0,Guid.NewGuid().ToString())!=0)return r;try{string[] f={p};if(RmRegisterResources(h,1,f,0,IntPtr.Zero,0,null)!=0)return r;uint need=0,got=0,reb=0;RmGetList(h,out need,ref got,null,ref reb);if(need==0)return r;var a=new PI[need];got=need;if(RmGetList(h,out need,ref got,a,ref reb)==0)for(uint i=0;i<got;i++)r.Add(a[i].Process.PID);}finally{RmEndSession(h);}return r;}}
'@
Add-Type -TypeDefinition $rmSrc -Language CSharp

# Exclude self so a scheduled DummyLedgerVacuum run doesn't disable its own task.
$tasks = Get-ScheduledTask -TaskName "Dummy*" | Where-Object { $_.TaskName -ne "DummyLedgerVacuum" }
try {
    Write-Host "=== disabling $($tasks.Count) Dummy* tasks (pausing the runtime) ==="
    foreach ($t in $tasks) {
        try { Disable-ScheduledTask -TaskName $t.TaskName -ErrorAction Stop | Out-Null }
        catch { Write-Host "  disable DENIED $($t.TaskName) (elevated?): $($_.Exception.Message)" }
    }

    Write-Host "=== killing running Dummy python processes (not the dashboard) ==="
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -match "run_dummy|shadow_daemon" -and $_.CommandLine -notmatch "run_dummy_dashboard.py|run_dummy_tote" } |
        ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force; Write-Host "  killed $($_.ProcessId)" } catch {} }

    Write-Host "=== waiting until nothing holds the ledger ==="
    $clear = $false
    for ($i = 0; $i -lt 60; $i++) {
        $h = [RMV]::H($ledger)
        if ($h.Count -eq 0) { $clear = $true; break }
        Write-Host "  still held by: $($h -join ', ') -- waiting"
        Start-Sleep -Seconds 5
    }
    if (-not $clear) { throw "ledger still held after 5min; aborting VACUUM (tasks will re-enable)" }

    Write-Host "=== VACUUM (exclusive; ~minutes) ==="
    $before = (Get-Item $ledger).Length
    & $python -c "import sqlite3,time; t=time.time(); c=sqlite3.connect(r'$ledger'); c.execute('PRAGMA busy_timeout=600000'); c.execute('VACUUM'); c.close(); print('VACUUM done in %.0fs' % (time.time()-t))"
    $after = (Get-Item $ledger).Length
    Write-Host ("=== ledger {0:N1}GiB -> {1:N1}GiB (reclaimed {2:N1}GiB) ===" -f ($before/1GB), ($after/1GB), (($before-$after)/1GB))
}
finally {
    Write-Host "=== re-enabling all Dummy* tasks ==="
    foreach ($t in $tasks) { try { Enable-ScheduledTask -TaskName $t.TaskName -ErrorAction Stop | Out-Null } catch { Write-Host "  enable DENIED $($t.TaskName)" } }
    Write-Host "done."
}
