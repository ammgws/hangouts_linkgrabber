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
    """Used to extract links from Hangouts message body."""
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
@click.option(
    '--include-self',
    default=False,
    is_flag=True,
    help='Set whether or not to include links sent by user.',
)
def main(config_path, cache_path, before, after, include_self):
    """Catch up on links sent during the day from a specified Hangouts contact.
    Hangouts messages are parsed through Gmail API.
    """
    configure_logging(cache_path)

    config_file = os.path.join(config_path, 'linkgrabber.ini')
    logging.debug('Using config file: %s.', config_file)
    config = ConfigParser()
    config.read(config_file)

    # This can be either a (partial) name or e-mail address.
    chat_partner = config.get('Settings', 'chat_partner')

    gmail_client_id = config.get('Gmail', 'client_id')
    gmail_client_secret = config.get('Gmail', 'client_secret')
    gmail_token_file = os.path.join(cache_path, 'gmail_cached_token')
    if not os.path.isfile(gmail_token_file):
        Path(gmail_token_file).touch()

    hangouts_client_id = config.get('Hangouts', 'client_id')
    hangouts_client_secret = config.get('Hangouts', 'client_secret')
    hangouts_token_file = os.path.join(cache_path, 'hangouts_cached_token')
    if not os.path.isfile(hangouts_token_file):
        Path(hangouts_token_file).touch()

    # Setup Google OAUTH instance for acccessing Gmail.
    gmail_scopes = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/userinfo.email',
    ]
    oauth = GoogleAuth(gmail_client_id, gmail_client_secret, gmail_scopes, gmail_token_file)
    oauth.authenticate()

    # Get email address so we can filter out messages sent by user later on.
    user = oauth.get_email()

    # Retrieves all Hangouts chat messages received between 'before_time' and 'after_time' on the current day.
    logging.debug('Getting emails for: %s', user)
    current_date = dt.datetime.today()
    before_time = int(current_date.replace(hour=before.hour, minute=before.minute).timestamp())
    after_time = int(current_date.replace(hour=after.hour, minute=after.minute).timestamp())
    base_url = 'https://www.googleapis.com/gmail/v1/users/me/messages'
    authorization_header = {'Authorization': 'OAuth %s' % oauth.access_token}
    s = requests.Session()
    s.headers.update(authorization_header)

    # Note 'is:chat' is valid as well: https://support.google.com/mail/answer/7190
    if include_self:
        params = {'q': f'in:chats from:{chat_partner} OR to:{chat_partner} after:{after_time} before:{before_time}'}
    else:
        params = {'q': f'in:chats from:{chat_partner} after:{after_time} before:{before_time}'}

    # For response format refer to https://developers.google.com/gmail/api/v1/reference/users/messages/list
    r = s.get(base_url, params=params)
    response = r.json()

    messages = []
    if 'messages' in response:
        messages.extend(response['messages'])

    while 'nextPageToken' in response:
        params['pageToken'] = response['nextPageToken']
        r = s.get(base_url, params=params)
        response = r.json()
        messages.extend(response['messages'])

    # Extract links from chat logs.
    links = []
    parser = LinkParser()
    for message in messages:
        # For response format refer to https://developers.google.com/gmail/api/v1/reference/users/messages
        url = f'{base_url}/{message["id"]}?'
        r = s.get(url)

        if r.status_code == 200:
            data = json.loads(r.text)  # requests' json() method seems to have issues handling this response
            sender = data['payload']['headers'][0]['value']
            decoded_raw_text = base64.urlsafe_b64decode(data['payload']['body']['data']).decode('utf-8')

            if 'href' in decoded_raw_text:
                parser.feed(decoded_raw_text)
                link = parser.link

                if include_self:
                    links.append(link)
                elif user not in sender:
                    links.append(link)
    else:
        logging.info('No messages found.')

    if links:
        message = 'Links from today:\n' + ' \n\n'.join(links)

        hangouts = HangoutsClient(hangouts_client_id, hangouts_client_secret, hangouts_token_file)
        if hangouts.connect():
            hangouts.process(block=False)
            sleep(5)  # Need time for Hangouts roster to update.
            hangouts.send_to_all(message)
            hangouts.disconnect(wait=True)
            logging.info('Finished sending message.')
        else:
            logging.error('Unable to connect to Hangouts.')
    else:
        logging.info('No links found.')


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
