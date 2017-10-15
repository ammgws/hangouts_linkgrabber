# hangouts_linkgrabber
Catch up on links sent during the day from a specified Hangouts contact.

## Why?
My friend and I often exchange links in our Hangouts chats, but during weekdays at work we may not be able to check the link straight away and forget to follow through when we get home. Thus this script was written so that at the end of the day we will get sent a list of links we sent each other during working hours.

##### Requirements
* GMail or Google Apps account which can use Hangouts
* Python 3.6+

##### Installation
git clone https://github.com/ammgws/hangouts_linkgrabber.git  
cd hangouts_linkgrabber  
pip install -r requirements.txt  

##### Before Use
1. Go to [Google APIs](https://console.developers.google.com/apis/) and generate secret client ID/password.
2. Fill in values in `linkgrabber.ini`

##### Usage

##### Run via systemd timer
Example, once per day at 11.30am:

Create the following user units in `~/.config/systemd/user`
(may have to create if not existing):

`wynbot.timer`
```
[Unit]
Description=Run linkgrabber once daily

[Timer]
OnCalendar=*-*-* 18:00:00

[Install]
WantedBy=timers.target
```

`linkgrabber.service`
```
[Unit]
Description=Runs hangouts-linkgrabber.

[Service]
Type=simple
ExecStart=/path/to/venv/bin/python /path/to/hangouts_linkgrabber/linkgrabber.py

[Install]
WantedBy=default.target
```
Enable with `systemctl --user enable wynbot.timer`
(note do NOT use sudo)

##### Run via crontab
Example, once per day at 6pm:
```
LINKGRAB_DIR = /path/to/hangouts_linkgrabber
LINKGRAB_VENV = /path/to/yourvirtualenv/bin/python
00 18 * * * $LINKGRAB_VENV $LINKGRAB_DIR/linkgrabber.py 2>&1
```
