@echo off
REM nettoyer_sql_obsolete.cmd - Range le fichier SQL piege sans le supprimer.
REM Il contient des commentaires -- et des blocs DO $$ avec ENUM : la construction
REM exacte qui a fait planter Supabase le 16 juin 2026.
REM Ce script RENOMME seulement. Rien n'est efface. Reversible a la main.

cd /d "%~dp0\.."
setlocal

set CIBLE=sql\001_mcp_servers_and_bridges.sql
set NOUVEAU=sql\001_mcp_servers_and_bridges.sql.OBSOLETE

echo ================================================
echo  YggNexus - rangement du SQL obsolete
echo ================================================
echo.

if not exist "%CIBLE%" (
  echo Rien a faire : %CIBLE% est deja range ou absent.
  goto fin
)

if exist "%NOUVEAU%" (
  echo Un fichier .OBSOLETE existe deja. Je ne touche a rien.
  echo Verifie sql\ a la main.
  goto fin
)

ren "%CIBLE%" "001_mcp_servers_and_bridges.sql.OBSOLETE"
if errorlevel 1 goto erreur

echo Renomme : %CIBLE%
echo      vers : %NOUVEAU%
echo.
echo Le fichier est toujours sur le disque. Rien n'a ete supprime.
goto fin

:erreur
echo.
echo ECHEC du renommage. Le fichier est peut-etre ouvert dans un editeur.
echo Ferme-le et relance.

:fin
echo.
pause
