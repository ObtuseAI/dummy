' Hidden launcher: a SECOND, read-only dashboard bound to this node's
' Tailscale interface IP so the phone (and any tailnet device) can reach the
' operator board, while the primary loopback dashboard task is left untouched.
' Binding to the specific tailnet IP (not 0.0.0.0) means it is reachable ONLY
' over the encrypted Tailscale tunnel, never the broadcast LAN, and it does not
' collide with the loopback :8787 the admin-owned DummyDashboard task holds.
' The write/control endpoints stay loopback-origin guarded on the host.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"

' Resolve the Tailscale IPv4 for this node at launch (stable per node, but
' resolved fresh so a re-keyed tailnet still binds correctly).
Set exec = shell.Exec("tailscale ip -4")
tsip = ""
Do While Not exec.StdOut.AtEndOfStream
    line = Trim(exec.StdOut.ReadLine())
    If Len(line) > 0 And tsip = "" Then tsip = line
Loop
If tsip = "" Then tsip = "100.98.141.113"   ' frankenstein fallback

Set env = shell.Environment("PROCESS")
env("DUMMY_DASHBOARD_HOST") = tsip
env("DUMMY_DASHBOARD_STDIO_LOG") = shell.CurrentDirectory & "\runtime\autonomy\dashboard_tailnet_stdout.log"

shell.Run "C:\Python314\pythonw.exe scripts\run_dummy_dashboard.py --port 8787 --host " & tsip, 0, False
