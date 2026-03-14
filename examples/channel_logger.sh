#!/bin/bash
# Log all messages from a specific channel to a file.
#
# Usage:
#   ./examples/channel_logger.sh "#general" messages.log
#
# Outputs JSONL — one JSON object per event.

CHANNEL="${1:?Usage: $0 <channel> <logfile>}"
LOGFILE="${2:?Usage: $0 <channel> <logfile>}"

echo "Logging #${CHANNEL} to ${LOGFILE}..."

discli listen --json --channel "$CHANNEL" --events messages | while read -r event; do
    echo "$event" >> "$LOGFILE"

    # Print a summary to terminal
    author=$(echo "$event" | jq -r '.author')
    content=$(echo "$event" | jq -r '.content')
    echo "[$(date +%H:%M:%S)] ${author}: ${content}"
done
