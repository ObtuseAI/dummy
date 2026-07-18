' Hidden launcher (Wave-27): runs one vNext shadow-runtime ignition pass with
' a working directory and append-redirected log, NO console window. The
' scheduled task points here instead of `cmd /c ...` so nothing flashes on the
' desktop. Regular python.exe (not pythonw) so stdout/stderr are real handles
' the redirect captures -- the shadow pass prints a one-line JSON summary.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
shell.Run "cmd /c C:\Python314\python.exe scripts\run_dummy_vnext_shadow.py >> runtime\autonomy\vnext_shadow_stdout.log 2>&1", 0, False
