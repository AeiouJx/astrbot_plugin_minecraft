@echo off
REM Deploy to AstrBot server via SSH
set SERVER=cat@8.134.252.229
set SSH_KEY=~\.ssh\id_ed25519_badapple
set REMOTE_DIR=/home/cat/Astrbot/data/plugins/astrbot_plugin_minecraft_bridge

echo [1/4] Creating zip...
cd /d "%~dp0\.."
powershell -Command "Remove-Item -Force '%TEMP%\mcbridge.zip' -ErrorAction SilentlyContinue; Compress-Archive -Path 'main.py','__init__.py','metadata.yaml','requirements.txt','_conf_schema.json','LICENSE','adapter','bridge','tools','pages' -DestinationPath '%TEMP%\mcbridge.zip' -Force"

echo [2/4] Uploading...
scp -i %SSH_KEY% "%TEMP%\mcbridge.zip" %SERVER%:/tmp/mcbridge.zip

echo [3/4] Extracting...
ssh -i %SSH_KEY% %SERVER% "cd /tmp && unzip -o mcbridge.zip -d mcbridge_deploy > /dev/null 2>&1 && cp -rf mcbridge_deploy/* %REMOTE_DIR%/ && rm -rf /tmp/mcbridge_deploy /tmp/mcbridge.zip && echo DEPLOYED"

echo [4/4] Done! Reload plugin in AstrBot WebUI.
pause
