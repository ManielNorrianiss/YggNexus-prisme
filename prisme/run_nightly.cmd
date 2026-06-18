@echo off
REM run_nightly.cmd - Wrapper Windows pour l'orchestrateur nocturne YggNexus.
REM Lance run_nightly.py depuis le dossier prisme.
REM Usage : run_nightly.cmd [options passes a run_nightly.py]
REM         run_nightly.cmd --dry-run
REM         run_nightly.cmd --from export
REM         run_nightly.cmd --stop-on-warning

cd /d "%~dp0"
python run_nightly.py %*
