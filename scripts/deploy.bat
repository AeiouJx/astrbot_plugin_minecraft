@echo off
REM Deploy to AstrBot server via git push
set SSH_KEY=%USERPROFILE%\.ssh\id_ed25519_badapple

echo Pushing to deploy remote...
set GIT_SSH_COMMAND=ssh -i %SSH_KEY%
git push deploy master

echo Done! Plugin auto-deployed via post-receive hook.
echo Reload plugin in AstrBot WebUI if needed.
