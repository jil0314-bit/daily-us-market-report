@echo off
setlocal
cls
echo ========================================
echo Telegram Send Test
echo ========================================
echo.
echo Paste your Telegram bot token below.
echo Do NOT paste it into ChatGPT.
echo.
set /p TELEGRAM_BOT_TOKEN=Telegram bot token: 
echo.
echo Telegram chat id is probably: 6293328963
echo Paste chat id below.
echo.
set /p TELEGRAM_CHAT_ID=Telegram chat id: 
echo.
echo Sending test message...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$token=$env:TELEGRAM_BOT_TOKEN; $chat=$env:TELEGRAM_CHAT_ID; $url='https://api.telegram.org/bot' + $token + '/sendMessage'; $body=@{chat_id=$chat;text='Telegram test success. Daily US market report will be sent here.'}; Invoke-RestMethod -Method Post -Uri $url -Body $body"
if errorlevel 1 (
  echo.
  echo FAILED. Check token and chat id.
) else (
  echo.
  echo SUCCESS. Check your Telegram bot chat.
)
pause
