#!/bin/bash

# Wake up the Render web service (it may be cold on free tier)
echo "⏰ Warming up web service..."
curl -s https://paqi-report.onrender.com/ > /dev/null

# Wait a few seconds for it to fully wake up
sleep 10

# Trigger the daily report generation
echo "📡 Sending POST to /generate-daily-report..."
curl -X POST https://paqi-report.onrender.com/generate-daily-report

echo "✅ Done."