@echo off
setlocal
title MiniSumos RC - Iniciar dashboard
cd /d "%~dp0"

set "RULE=MiniSumos RC Dashboard - Hotspot (TCP 8000)"

echo ==========================================
echo       MINISUMOS RC - DASHBOARD
echo ==========================================
echo.

REM Si la regla ya existe, no se solicita permiso de administrador.
netsh advfirewall firewall show rule name="%RULE%" >nul 2>&1
if not errorlevel 1 goto iniciar

echo Se necesita configurar el acceso por el hotspot de Windows.
echo Aparecera una ventana de Windows para autorizar el cambio.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'powershell.exe' -Verb RunAs -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0permitir_hotspot.ps1""'"

REM Comprobar que la regla se haya creado; puede haberse cancelado el permiso UAC.
netsh advfirewall firewall show rule name="%RULE%" >nul 2>&1
if errorlevel 1 goto error_regla

:iniciar
echo Regla de firewall disponible.
echo Iniciando dashboard...
echo.
echo En este PC: http://127.0.0.1:8000
echo Desde el hotspot: http://192.168.137.1:8000
echo.
echo Para detener el servidor, presiona Ctrl+C.
echo ==========================================
echo.

where py >nul 2>&1
if not errorlevel 1 (
    py -3 app.py
) else (
    python app.py
)
if errorlevel 1 goto error_servidor
goto fin

:error_regla
echo.
echo ERROR: No se pudo confirmar la regla del firewall.
echo Si cancelaste la ventana de permisos, vuelve a ejecutar este archivo
echo y acepta la solicitud. Tambien verifica que permitir_hotspot.ps1
echo este en la misma carpeta.
pause
exit /b 1

:error_servidor
echo.
echo ERROR: No se pudo iniciar el servidor.
echo Verifica que Python, Flask y los archivos del proyecto esten instalados.
pause
exit /b 1

:fin
endlocal
