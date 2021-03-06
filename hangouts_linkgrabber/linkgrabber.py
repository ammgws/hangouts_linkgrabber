#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import datetime as dt
import logging
import os.path
from configparser import ConfigParser
from html.parser import HTMLParser
from operator import itemgetter
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
        self.links = []
        self.extract = False

    def reset(self):
        self.links = []
        self.extract = False
        return super().reset()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'href' in attrs:
            self.extract = True

    def handle_data(self, data):
        if self.extract:
            self.links.append(data)
            self.extract = False

    def handle_endtag(self, tag):
        self.extract = False

    def error(self, message):
        pass


def create_search_args(start_time, end_time):
    """Generate timestamps to use in GMail search query.

    Input: start_time - time object
           end_time - time object

    Returns: tuple (start, end) of Unix timestamps in whole seconds.

    """
    current_date = dt.datetime.today()
    if start_time >= end_time:
        correction = dt.timedelta(days=1)
    else:
        correction = dt.timedelta(days=0)

    start_datetime = current_date.replace(hour=start_time.hour, minute=start_time.minute) - correction
    end_datetime = current_date.replace(hour=end_time.hour, minute=end_time.minute)

    return int(start_datetime.timestamp()), int(end_datetime.timestamp())


def validate_time(ctx, param, time_str):
    try:
        parsed_time = dt.datetime.strptime(time_str, '%H%M')
        return parsed_time.time()
    except ValueError:
        raise click.BadParameter(f'Time should be in HHMM format. You gave "{time_str}"')


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
    '--start-time',
    default='0830',
    callback=validate_time, expose_value=True,
    help='Start time in 24hr HHMM format. Default 0830.',
)
@click.option(
    '--end-time',
    default='1730',
    callback=validate_time, expose_value=True,
    help='End time in 24hr HHMM format. Default 1730.',
)
@click.option(
    '--include-self',
    default=False,
    is_flag=True,
    help='Set to also include links sent by yourself.',
)
@click.option(
    '--show-time',
    default=False,
    is_flag=True,
    help='Set to show the time links were sent in output message.',
)
def main(config_path, cache_path, start_time, end_time, include_self, show_time):
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
    start_timestamp, end_timestamp = create_search_args(start_time, end_time)
    base_url = 'https://www.googleapis.com/gmail/v1/users/me/messages'
    authorization_header = {'Authorization': 'OAuth %s' % oauth.access_token}
    s = requests.Session()
    s.headers.update(authorization_header)

    # Note 'is:chat' is valid as well: https://support.google.com/mail/answer/7190
    if include_self:
        params = {'q': f'in:chats from:{chat_partner} OR to:{chat_partner} after:{start_timestamp} before:{end_timestamp}'}
    else:
        params = {'q': f'in:chats from:{chat_partner} after:{start_timestamp} before:{end_timestamp}'}

    # For response format refer to https://developers.google.com/gmail/api/v1/reference/users/messages/list
    logging.debug('Getting emails for: %s between %s and %s', user, dt.datetime.fromtimestamp(start_timestamp), dt.datetime.fromtimestamp(end_timestamp))
    r = s.get(base_url, params=params)
    response = r.json()

    messages = []
    links = []
    if 'messages' in response:
        messages.extend(response['messages'])

        while 'nextPageToken' in response:
            params['pageToken'] = response['nextPageToken']
            r = s.get(base_url, params=params)
            response = r.json()
            messages.extend(response['messages'])

        # Extract links from chat logs.
        parser = LinkParser()
        for message in messages:
            # For response format refer to https://developers.google.com/gmail/api/v1/reference/users/messages
            url = f'{base_url}/{message["id"]}?'
            r = s.get(url)

            if r.status_code == 200:
                data = r.json()

                sender = data['payload']['headers'][0]['value']
                msg_time = dt.datetime.fromtimestamp(int(data['internalDate'])/1000).strftime('%H:%M:%S')  # Google returns epoch in ms
                msg_body = base64.urlsafe_b64decode(data['payload']['body']['data']).decode('utf-8')

                if 'href' in msg_body:
                    parser.feed(msg_body)
                    links.extend([
                            {
                                'url': parser.links,
                                'sender': sender,
                                'time': msg_time,
                            }])
                    parser.reset()
        parser.close()
    else:
        logging.info('No messages found.')

    s.close()

    if links:
        # TODO: is there a better way?
        message_parts = []
        for link in sorted(links, key=itemgetter('time')):
            if include_self:
                link_part = ', '.join(link['url'])
            else:
                if user not in link['sender']:
                    link_part = ', '.join(link['url'])

            if show_time:
                time_part = f'[{link["time"]}] '
            else:
                time_part = ''

            message_parts.extend([f'{time_part}{link_part}'])
            message = 'Links from today:\n' + ' \n\n'.join(message_parts)

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
