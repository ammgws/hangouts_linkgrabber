# hangouts_linkgrabber
Catch up on links sent during the day from a specified Hangouts contact.

##### Why?
My friend and I often exchange links in our Hangouts chats, but during weekdays at work we may not be able to check the link straight away and forget to follow through when we get home.

##### Example
`linkgrabber.py --start-time 2230 --end-time 0930`
 > Links from today:  
 > [22:47:03] wwm.org  
 > [05:40:12] https://i.imgur.com/yarp.gifv  
 > [09:17:04] http://home.mellicon.com/info/90kg/  

##### Usage
> Usage: linkgrabber.py [OPTIONS]
>  
>  Catch up on links sent during the day from a specified Hangouts contact. Hangouts messages are parsed through Gmail API.
>  
> Options:  
>  --config-path PATH  Path to directory containing config file. Defaults to XDG config dir.  
>  --cache-path PATH   Path to directory to store logs and OAUTH tokens. Defaults to XDG cache dir.  
>  --start-time TEXT   Start time in 24hr HHMM format. Default 0830.  
>  --end-time TEXT     End time in 24hr HHMM format. Default 1730.  
>  --include-self      Set to also include links sent by yourself.  
>  --show-time         Set to show the time links were sent in output message.  
>  --help              Show this message and exit.  

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

##### Run via systemd timer
Example, once per day at 11.30am:

Create the following user units in `~/.config/systemd/user`:

`linkgrabber.timer`
```
[Unit]
Description=Run linkgrabber once daily.

[Timer]
OnCalendar=*-*-* 11:30:00

[Install]
WantedBy=timers.target
```

`linkgrabber.service`
```
[Unit]
Description=Run hangouts-linkgrabber.

[Service]
Type=simple
ExecStart=/path/to/venv/bin/python /path/to/hangouts_linkgrabber/linkgrabber.py

[Install]
WantedBy=default.target
```
Enable with `systemctl --user enable linkgrabber.timer`
(note do NOT use sudo)

##### Run via crontab
Example, once per day at 6pm:
```
LINKGRAB_DIR = /path/to/hangouts_linkgrabber
LINKGRAB_VENV = /path/to/yourvirtualenv/bin/python
00 18 * * * $LINKGRAB_VENV $LINKGRAB_DIR/linkgrabber.py 2>&1
```
