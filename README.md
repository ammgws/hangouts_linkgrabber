# hangouts_linkgrabber
Catch up on links sent during the day from a specified Hangouts contact.

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


##### Run via crontab
Example, once per day at 6pm:
```
LINKGRAB_DIR = /path/to/hangouts_linkgrabber
LINKGRAB_VENV = /path/to/yourvirtualenv/bin/python
00 18 * * * $LINKGRAB_VENV $LINKGRAB_DIR/linkgrabber.py 2>&1
```
