@echo off
echo Setting up MusicBot environment...

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed! Please install Python 3.8 or higher.
    pause
    exit
)

:: Create and activate virtual environment
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate

:: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

:: Install requirements
echo Installing dependencies...
pip install discord.py python-dotenv yt-dlp PyNaCl ffmpeg-python aiohttp

:: Create .env file if it doesn't exist
if not exist .env (
    echo Creating .env file...
    echo DISCORD_TOKEN=your_bot_token_here > .env
    echo Please edit .env file and add your Discord bot token
)

:: Download FFmpeg if not present
if not exist "bin\ffmpeg" (
    echo Creating FFmpeg directory...
    mkdir "bin\ffmpeg"
    echo Please download FFmpeg from https://ffmpeg.org/download.html
    echo and place ffmpeg.exe in the bin\ffmpeg folder
)

echo Setup completed!
echo Don't forget to:
echo 1. Add your Discord bot token to .env file
echo 2. Download and add FFmpeg to bin\ffmpeg folder
pause