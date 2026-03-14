#!/bin/bash
# Create a poll using reactions.
#
# Sends a message with a question, adds reaction options,
# then checks results after a delay.
#
# Usage:
#   ./examples/reaction_poll.sh "#general" "What should we build next?"

CHANNEL="${1:?Usage: $0 <channel> <question>}"
QUESTION="${2:?Usage: $0 <channel> <question>}"

# Send the poll message
RESULT=$(discli --json message send "$CHANNEL" "📊 **Poll:** ${QUESTION}

1️⃣ Option A
2️⃣ Option B
3️⃣ Option C")

MSG_ID=$(echo "$RESULT" | jq -r '.id')
echo "Poll created (message ID: $MSG_ID)"

# Add reaction options
discli reaction add "$CHANNEL" "$MSG_ID" "1️⃣"
discli reaction add "$CHANNEL" "$MSG_ID" "2️⃣"
discli reaction add "$CHANNEL" "$MSG_ID" "3️⃣"

echo "Reactions added. Check results later with:"
echo "  discli reaction list $CHANNEL $MSG_ID"
