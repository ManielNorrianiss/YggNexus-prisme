@echo off
echo Creation de la tache planifiee YggNexus_nightly (chaque nuit a 03:00)...
echo.
schtasks /create /tn "YggNexus_nightly" /tr "D:\Emperor\YggNexus\prisme\run_nightly.cmd" /sc daily /st 03:00 /f
echo.
echo Si tu vois SUCCESS ci-dessus, c'est planifie. Tu peux fermer cette fenetre.
pause
