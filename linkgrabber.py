#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Standard library
import base64
import datetime as dt
import json
import logging
import os.path
from configparser import ConfigParser
from html.parser import HTMLParser
from pathlib import Path
from time import sleep
# Third party
import click
import requests
from google_auth import GoogleAuth
from hangoutsclient import HangoutsClient


APP_NAME = 'hangouts_linkgrabber'


class LinkParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.link = []
        self.last_tag = None

    def handle_starttag(self, tag, attr):
        self.last_tag = tag.lower()

    def handle_data(self, data):
        if self.last_tag == 'a' and data.strip():
            self.link = data

    def error(self, message):
        pass


def validate_time(ctx, param, time_str):
    try:
        time = dt.datetime.strptime(time_str, '%H%M')
        return time
    except ValueError:
        raise click.BadParameter('Time should be in HHMM format')


def create_dir(ctx, param, directory):
    if not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    return directory


@click.command()
@click.option(
    '--config-path',
    type=click.Path(),
    default=os.path.join(os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')), APP_NAME),
    callback=create_dir,
    help='Path to directory containing config file. Defaults to XDG config dir.',
)
@click.option(
    '--cache-path',
    type=click.Path(),
    default=os.path.join(os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache')), APP_NAME),
    callback=create_dir,
    help='Path to directory to store logs and such. Defaults to XDG cache dir.',
)
@click.option(
    '--after', '-a',
    default='0830',
    callback=validate_time, expose_value=True,
    help='"after" time in hhmm format. Default 0830.',
)
@click.option(
    '--before', '-b',
    default='1730',
    callback=validate_time, expose_value=True,
    help='"before" time in hhmm format. Default 1730.',
)
def main(config_path, cache_path, before, after):
    """Catch up on links sent during the day from a specified Hangouts contact.
    Hangouts messages are parsed through Gmail API.

    OAuth for devices doesn't support Hangouts or Gmail scopes, so have to send auth link through the terminal.
    https://developers.google.com/identity/protocols/OAuth2ForDevices
    """
    configure_logging(cache_path)

    config_file = os.path.join(config_path, 'linkgrabber.ini')
    logging.debug('Using config file: %s.', config_file)
    config = ConfigParser()
    config.read(config_file)
    chat_partner = config.get('Settings', 'chat_partner')  # Name or email of the chat partner to search chat logs for
    gmail_client_id = config.get('Gmail', 'client_id')
    gmail_client_secret = config.get('Gmail', 'client_secret')
    gmail_refresh_token = os.path.join(cache_path, 'gmail_refresh_token')
    if not os.path.isfile(gmail_refresh_token):
        Path(gmail_refresh_token).touch()
    hangouts_client_id = config.get('Hangouts', 'client_id')
    hangouts_client_secret = config.get('Hangouts', 'client_secret')
    hangouts_refresh_token = os.path.join(cache_path, 'hangouts_refresh_token')
    if not os.path.isfile(hangouts_refresh_token):
        Path(hangouts_refresh_token).touch()

    # Setup Google OAUTH instance for acccessing Gmail.
    gmail_scopes = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/userinfo.email',
    ]
    oauth = GoogleAuth(gmail_client_id, gmail_client_secret, gmail_scopes, gmail_refresh_token)
    oauth.authenticate()

    # Get email address so we can filter out messages sent by user later on
    user = oauth.get_email()

    # Retrieves all Hangouts chat messages received between 'before_time' and 'after_time' on the current day
    logging.debug('Getting emails for: %s', user)
    current_date = dt.datetime.today()
    before_timestamp = int(current_date.replace(hour=before.hour, minute=before.minute).timestamp())
    after_timestamp = int(current_date.replace(hour=after.hour, minute=after.minute).timestamp())
    request_url = 'https://www.googleapis.com/gmail/v1/users/me/messages?q="after:{0} before:{1} from:{2}"'.format(
        after_timestamp, before_timestamp, chat_partner)
    logging.debug('URL for chat log search: %s', request_url)
    authorization_header = {'Authorization': 'OAuth %s' % oauth.access_token}
    resp = requests.get(request_url, headers=authorization_header)
    logging.debug('Authorisation result: %s', resp.status_code)
    data = resp.json()

    # Extract links from chat logs
    links = []
    parser = LinkParser()
    if 'messages' in data:
        for message in data['messages']:
            request_url = 'https://www.googleapis.com/gmail/v1/users/me/messages/{0}?'.format(message['id'])
            authorization_header = {'Authorization': 'OAuth %s' % oauth.access_token}
            resp = requests.get(request_url, headers=authorization_header)  # get message data
            logging.debug('Message query result: %s', resp.status_code)

            if resp.status_code == 200:
                data = json.loads(resp.text)  # requests' json() method seems to have issues handling this response
                sender = data['payload']['headers'][0]['value']
                # Since the gmail API doesn't appear to support the 'in:chats/is:chat' query anymore,
                # we end up pulling both emails and chat messages, but the data structures are different so
                # wrapping this in a try-except as a quick-and-dirty fix to ignore all email messages.
                try:
                    decoded_raw_text = base64.urlsafe_b64decode(data['payload']['body']['data']).decode('utf-8')
                except KeyError:
                    break

                # ignore messages sent by us, we only want links that chat partner has sent
                if user not in sender and 'href' in decoded_raw_text:
                    parser.feed(decoded_raw_text)
                    link = parser.link
                    links.append(link)
    else:
        logging.info('No messages found')

    if links:
        message = 'Links from today:\n' + ' \n'.join(links)
        # Setup Hangouts bot instance, connect and send message
        hangouts = HangoutsClient(hangouts_client_id, hangouts_client_secret, hangouts_refresh_token)
        if hangouts.connect():
            hangouts.process(block=False)
            sleep(5)  # need time for Hangouts roster to update
            hangouts.send_to_all(message)
            hangouts.disconnect(wait=True)
            logging.info('Finished sending message')
        else:
            logging.error('Unable to connect to Hangouts.')
    else:
        logging.info('No new links!')


def configure_logging(log_dir):
    # Configure root logger. Level 5 = verbose to catch mostly everything.
    logger = logging.getLogger()
    logger.setLevel(level=5)

    log_folder = os.path.join(log_dir, 'logs')
    if not os.path.exists(log_folder):
        os.makedirs(log_folder, exist_ok=True)

    log_filename = 'linkgrabber_{0}.log'.format(dt.datetime.now().strftime('%Y%m%d_%Hh%Mm%Ss'))
    log_filepath = os.path.join(log_folder, log_filename)
    log_handler = logging.FileHandler(log_filepath)

    log_format = logging.Formatter(
        fmt='%(asctime)s.%(msecs).03d %(name)-12s %(levelname)-8s %(message)s (%(filename)s:%(lineno)d)',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)
    # Lower requests module's log level so that OAUTH2 details aren't logged
    logging.getLogger('requests').setLevel(logging.WARNING)
    # Quieten SleekXMPP output
    # logging.getLogger('sleekxmpp.xmlstream.xmlstream').setLevel(logging.INFO)


if __name__ == '__main__':
    main()
