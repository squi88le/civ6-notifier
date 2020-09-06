# Civilization VI webhook notifier

## Why

I've been having issues getting Mac based Civ6 to use turn notification webhooks (it crashes and the webhook isn't called). 

So, this script takes a different approach. It parses the log files to work out what's happening and calls the webhook you configure.

## Installation & Configuration

### Dependencies

- You need Python 3
- You need ```requests```

```
python3 -m pip install requests
```

Put civ_event.py and config.json into a directory somewhere on your filesystem.

Configure your favourite scheduler to execute it every minute (for example).

Edit config.json and set the parameters as needed for your environment.

Note that any game name matching a filter will result in that webhook being fired and all filters 
are always considered. If and only if no filters match, the default webhook is fired. In this way 
it's possible to configure the game-room relationships 1:1, 1:N, N:1 or N:N as needed. 

```
{
    "webhooks": {
        "filters": [
            {
                "matches": ["Specific Game"],
                "webhook": "https://webhook1",
                "message": "{user} has committed a turn!"
            }
        ],
        "default": "https://webhook2",
        "message: "{user} just committed a turn in game {name} at {event_ts}"
    },
    "user":"InGameName",
    "log_file":"/Users/bob/Library/Application Support/Sid Meier's Civilization VI/Logs/net_connection_debug.log"
}
```

The ```message``` field is a template that can make use of a number of keywords, introduced in braces.

|Keyword|Meaning|
|---|---|
|user|Name of user|
|name|Name of game|
|lobby|Lobby number|
|event_ts|Time of event|
|join_ts|Time session was joined|
|match|Match Id|

## Usage

Try configuring to send a notification into a Discord channel!
