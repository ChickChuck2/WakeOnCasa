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
echo   [!] Certifique-se de que o caminho de rede está acessível.
echo.
echo   Serão copiados: Códigos backend, static UI, Dockerfile e configurações.
echo   Serão EXCLUÍDOS da cópia: .git, __pycache__, logs e temporários.
echo.
echo ========================================================
echo.

set /p confirmar="Confirmar cópia para o servidor? (S/N): "

if /i not "%confirmar%"=="S" (
    echo Operação cancelada pelo usuário.
    echo.
    pause
    exit
)

cls
echo ========================================================
echo   Iniciando cópia para o servidor...
echo ========================================================
echo.

:: Executa o Robocopy com os devidos filtros
:: /E - Copia subdiretórios, incluindo os vazios
:: /NP - Oculta a porcentagem de progresso para a tela ficar mais limpa
:: /COPY:DT - Copia apenas Dados (Data) e Timestamps (ignora atributos NTFS de segurança)
:: /NODCOPY - Não tenta copiar carimbos de data/hora de pastas (evita erro 5 no Samba)
:: /R:3 - Tenta novamente 3 vezes em caso de erro
:: /W:3 - Espera 3 segundos entre as tentativas
:: /XD - Exclui as pastas listadas (.git, __pycache__, venv)
:: /XF - Exclui arquivos temporários e logs
robocopy . "%DESTINO%" /E /NP /COPY:DT /NODCOPY /R:3 /W:3 /XD .git __pycache__ venv .venv /XF *.log *.tmp

echo.
echo ========================================================
echo   [✔] Cópia concluída com sucesso!
echo   [i] Para rodar no CasaOS, execute:
echo       docker compose up -d --build
echo ========================================================
echo.
pause
exit
