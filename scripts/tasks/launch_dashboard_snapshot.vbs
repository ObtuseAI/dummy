' Hidden launcher (Wave-42): refresh the dashboard snapshot artifact so the web
' dashboard reads a file instead of holding a SHARED lock on the ledger for a
' minutes-long backtest. --light refreshes only the cheap summaries most runs;
' the backtest refreshes when the prior one ages past the bound. No console
' window. Supervise the Python child so Task Scheduler's success/failure and
' IgnoreNew semantics cover the real refresh rather than a detached launcher.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
commandLine = "cmd.exe /d /s /c ""C:\Python314\python.exe scripts\run_dummy_dashboard_snapshot.py --light >> runtime\autonomy\dashboard_snapshot_stdout.log 2>&1"""
Set child = shell.Exec(commandLine)
deadline = DateAdd("n", 10, Now)
timedOut = False
Do While child.Status = 0
    If Now >= deadline Then
        ' Terminate the exact supervised command tree so cmd.exe cannot leave
        ' an orphaned Python refresh behind after a timeout.
        shell.Run "taskkill /PID " & child.ProcessID & " /T /F", 0, True
        If child.Status = 0 Then child.Terminate
        timedOut = True
        Exit Do
    End If
    WScript.Sleep 1000
Loop

If timedOut Then
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set logFile = fso.OpenTextFile("runtime\autonomy\dashboard_snapshot_stdout.log", 8, True)
    logFile.WriteLine "DASHBOARD_SNAPSHOT_TIMEOUT: supervised command tree terminated"
    logFile.Close
    WScript.Quit 124
End If
WScript.Quit child.ExitCode
