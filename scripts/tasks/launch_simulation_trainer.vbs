' Hidden launcher (Wave-15): simulation trainer, no console window.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
exitCode = shell.Run("cmd /c C:\Python314\python.exe C:\src\engine\dummy\scripts\run_dummy_simulation_training.py --summary >> C:\src\engine\dummy\runtime\autonomy\simulation_training_stdout.log 2>&1", 0, True)
WScript.Quit exitCode
