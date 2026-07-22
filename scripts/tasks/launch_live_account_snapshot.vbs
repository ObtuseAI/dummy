' Hidden supervised launcher for the authenticated GET-only Kalshi account
' snapshot. It never arms live submission, changes caps, or invokes an order
' method. The Python child redirects inherited descriptors before imports, so
' WshScriptExec pipes stay bounded and the launcher can safely wait.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
Set processEnvironment = shell.Environment("PROCESS")
processEnvironment("DUMMY_LIVE_ACCOUNT_STDIO_LOG") = shell.CurrentDirectory & "\runtime\autonomy\live_account_snapshot_stdout.log"
Set child = shell.Exec("C:\Python314\python.exe scripts\run_dummy_live_account_snapshot.py")
deadline = DateAdd("n", 2, Now)
timedOut = False
Do While child.Status = 0
    If Now >= deadline Then
        timedOut = True
        Exit Do
    End If
    WScript.Sleep 1000
Loop

If timedOut Then
    childPid = child.ProcessID
    If child.Status = 0 Then
        killResult = shell.Run("taskkill.exe /PID " & CStr(childPid) & " /T /F", 0, True)
    End If
    If child.Status = 0 Then child.Terminate
    On Error Resume Next
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set logFile = fso.OpenTextFile("runtime\autonomy\live_account_snapshot_stdout.log", 8, True)
    logFile.WriteLine "LIVE_ACCOUNT_SNAPSHOT_TIMEOUT: Python process tree terminated"
    logFile.Close
    On Error GoTo 0
    WScript.Quit 124
End If

WScript.Quit child.ExitCode
