' Hidden launcher (Wave-15): runs the shadow predator with a working
' directory and append-redirected log, with NO console window. The scheduled
' task points here instead of `cmd /c ...` so nothing flashes on the desktop.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
' Supervise the child directly.  The previous detached launch made Task
' Scheduler report success immediately, so IgnoreNew supervised only
' wscript.exe while failed Python children were invisible.  Keep the timeout
' here as well as in the installer because an administrator-owned legacy task
' may not be replaceable from a normal operator session.
Set processEnvironment = shell.Environment("PROCESS")
processEnvironment("DUMMY_SHADOW_STDIO_LOG") = shell.CurrentDirectory & "\runtime\autonomy\daemon_stdout.log"
Set child = shell.Exec("C:\Python314\python.exe scripts\run_dummy_shadow_daemon.py")
' Keep a two-minute margin ahead of the installer's default 15-minute Task
' Scheduler limit.  The launcher must remain alive long enough to kill the
' actual Python process tree and report timeout 124 itself.
deadline = DateAdd("n", 13, Now)
timedOut = False
Do While child.Status = 0
    If Now >= deadline Then
        timedOut = True
        Exit Do
    End If
    WScript.Sleep 1000
Loop

If timedOut Then
    ' Kill the exact live PID and its descendants before falling back to the
    ' direct WshScriptExec termination method.  The Status check prevents a
    ' recycled PID from ever reaching taskkill.
    childPid = child.ProcessID
    If child.Status = 0 Then
        killResult = shell.Run("taskkill.exe /PID " & CStr(childPid) & " /T /F", 0, True)
    End If
    If child.Status = 0 Then child.Terminate

    ' Python redirects both inherited OS descriptors to this same log before
    ' importing autonomy modules, so Exec's bounded pipes remain empty.  This
    ' append is best-effort and must not mask the timeout exit status.
    On Error Resume Next
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set logFile = fso.OpenTextFile("runtime\autonomy\daemon_stdout.log", 8, True)
    logFile.WriteLine "SHADOW_TASK_TIMEOUT: Python process tree terminated"
    logFile.Close
    On Error GoTo 0
    WScript.Quit 124
End If

WScript.Quit child.ExitCode
