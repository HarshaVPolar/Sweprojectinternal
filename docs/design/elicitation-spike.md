# Elicitation spike (ES-1)

Date: 2026-11-28. Purpose: find out whether the demonstration MCP client supports MCP elicitation, so that the approval gate (ADR-004) can use mode elicitation. The mode oob is built and tested whatever the result.

## How to test

1. Add this server to the MCP client configuration (for a client that uses a JSON configuration, add an entry under its mcpServers section; ask the client's documentation if the file is different):
   {"elicitation-spike": {"command": "/Users/dhanush/Desktop/Sweprojectinternal/.venv/bin/python", "args": ["/Users/dhanush/Desktop/Sweprojectinternal/scripts/spikes/elicitation_spike.py"]}}
2. Restart the client and make sure the server elicitation-spike is connected.
3. Ask the assistant: Call the tool ask_to_confirm with the item demo playlist. Then press Approve (accept) in the dialog.
4. Ask again, and this time press Decline.
5. Watch the stderr output of the server if the client shows it (the lines "elicitation requested at" and "elicitation answered at").
6. Remove the server from the client configuration after the test.

## Criteria

| ID | Criterion | How to observe |
|---|---|---|
| A | The client advertises the elicitation capability | the tool answer contains capability=true |
| B | The tool call blocks until the user answers | the assistant answers only after the dialog is answered; the stderr times are consistent |
| C | Accept and decline both return correctly | step 3 returns ACCEPTED and step 4 returns DECLINED |
| D | The prompt text is shown verbatim | the dialog shows the message including the item name |
| E | The model sees only the outcome | the tool answer has only the outcome word and the capability line |

The spike passes only when all five criteria are yes.

## Results

| ID | Result |
|---|---|
| A | not tested yet |
| B | not tested yet |
| C | not tested yet |
| D | not tested yet |
| E | not tested yet |

Client and version: not tested yet. Overall: not tested yet.
