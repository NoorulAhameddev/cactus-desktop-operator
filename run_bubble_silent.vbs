Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
PythonExe = "C:\Users\Nooru\.dodaios\.venv\Scripts\python.exe"
If Not FSO.FileExists(PythonExe) Then
    PythonExe = "python.exe"
End If
WshShell.Run """" & PythonExe & """ """ & ScriptDir & "\bubble_ui.py""", 0, False
