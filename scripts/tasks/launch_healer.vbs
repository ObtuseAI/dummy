' Hidden launcher (Wave-33): one self-heal / reconnect pass with NO console
' window. Regular python.exe (not pythonw) so stdout/stderr are real handles
' the redirect captures.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
exitCode = shell.Run("cmd /c C:\Python314\python.exe scripts\run_dummy_healer.py >> runtime\autonomy\healer_stdout.log 2>&1", 0, True)
WScript.Quit exitCode
