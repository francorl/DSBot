echo "Starting MusicBot..."

# Activate virtual environment (works for both Linux and Windows)
if [ -d "venv/Scripts" ]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Run the bot
python MusicBot.py