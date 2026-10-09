@echo off
REM lancer_mcp.cmd - Chaine complete de la verticale MCP, en un double-clic.
REM A lancer APRES avoir colle database\migration_mcp_vertical.sql dans Supabase.
REM Etape 1 : collecte du registre officiel, toutes les pages.
REM Etape 2 : construction du graphe pont (bridges).
REM Aucun push Supabase n'est fait ici : les deux scripts restent en dry-run.

cd /d "%~dp0"
setlocal

echo ================================================
echo  YggNexus - verticale MCP
echo ================================================
echo.
echo [1/2] Collecte du registre officiel (toutes les pages)...
echo.
python b1_mcp.py --limit 100 --max-pages 0 --enrich-github
if errorlevel 1 goto erreur

echo.
echo [2/2] Construction du graphe pont...
echo.
python b5_bridges_mcp.py
if errorlevel 1 goto erreur

echo.
echo ================================================
echo  TERMINE. Sorties dans prisme\data\.
echo  Le nombre de serveurs collectes est affiche
echo  a la ligne UNIQUE ci-dessus.
echo ================================================
goto fin

:erreur
echo.
echo ================================================
echo  ECHEC. Copie l'erreur ci-dessus et donne-la
echo  a Emperor.
echo ================================================

:fin
echo.
pause
endlocal
