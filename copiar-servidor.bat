@echo off
chcp 65001 > nul
title WakeOnCasa - Copiar para o Servidor CasaOS
cls

set "DESTINO=\\linux\root\DATA\AppData\WakeOnCasa"

echo ========================================================
echo   Copiar WakeOnCasa para o Servidor CasaOS (Robocopy)
echo ========================================================
echo.
echo   Destino: %DESTINO%
echo.
echo   [*] Certifique-se de que o caminho de rede esta acessivel.
echo.
echo   Serao copiados: Codigos backend, static UI, Dockerfile e configuracoes.
echo   Serao EXCLUIDOS da copia: .git, __pycache__, logs, data e temporarios.
echo.
echo ========================================================
echo.

set /p confirmar="Confirmar copia para o servidor? (S/N): "

if /i not "%confirmar%"=="S" (
    echo Operacao cancelada pelo usuario.
    echo.
    pause
    exit
)

cls
echo ========================================================
echo   Iniciando copia para o servidor...
echo ========================================================
echo.

robocopy . "%DESTINO%" /E /NP /COPY:DT /NODCOPY /R:3 /W:3 /XD .git __pycache__ venv .venv data /XF *.log *.tmp

echo.
echo ========================================================
echo   [OK] Copia concluida com sucesso!
echo   [i] Para rodar no CasaOS, execute no servidor:
echo       docker compose up -d --build
echo ========================================================
echo.
pause
exit
