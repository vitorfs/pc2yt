import argparse
import httplib
import httplib2
import os
import random
import time
import subprocess

import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow

from oauth2client import client
from oauth2client import file
from oauth2client import tools

from decouple import config
import requests
import feedparser


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIOS_DIR = os.path.join(BASE_DIR, 'audios')
VIDEOS_DIR = os.path.join(BASE_DIR, 'videos')
BACKGROUND_IMAGE = os.path.join(BASE_DIR, 'background.png')
LAST_PODCAST_FILE = os.path.join(BASE_DIR, '.last')
FEED_URL = config('FEED_URL')

httplib2.RETRIES = 1
MAX_RETRIES = 10
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, httplib.NotConnected,
    httplib.IncompleteRead, httplib.ImproperConnectionState,
    httplib.CannotSendRequest, httplib.CannotSendHeader,
    httplib.ResponseNotReady, httplib.BadStatusLine)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, 'client_secret.json')
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'youtube.dat')
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
VALID_PRIVACY_STATUSES = ('public', 'private', 'unlisted')


class Podcast(object):
    def __init__(self, title, description, url):
        self.title = title
        self.description = description
        self.url = url
        self.category = '22'  # see youtube categories IDs
        self.keywords = ''
        self.privacyStatus = 'private'
        self.video_file = None
        self.audio_file = None


def get_authenticated_service():
    '''flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_console()
    return build(API_SERVICE_NAME, API_VERSION, credentials = credentials)'''

    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, parents=[tools.argparser])
    flags = parser.parse_args([])

    flow = client.flow_from_clientsecrets(CLIENT_SECRETS_FILE, scope=SCOPES, message=tools.message_if_missing(CLIENT_SECRETS_FILE))

    storage = file.Storage(CREDENTIALS_FILE)
    credentials = storage.get()
    if credentials is None or credentials.invalid:
        credentials = tools.run_flow(flow, storage)
    http = credentials.authorize(http=httplib2.Http())

    # Build the service object.
    youtube = build(API_SERVICE_NAME, API_VERSION, http=http)

    return youtube


def initialize_upload(youtube, options):
    tags = None
    if options.keywords:
        tags = options.keywords.split(',')
    body=dict(
        snippet=dict(
            title=options.title,
            description=options.description,
            tags=tags,
            categoryId=options.category
        ),
        status=dict(
            privacyStatus=options.privacyStatus
        )
    )
    insert_request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=MediaFileUpload(options.video_file, chunksize=-1, resumable=True)
    )
    resumable_upload(insert_request)


def resumable_upload(request):
    response = None
    error = None
    retry = 0
    while response is None:
        try:
            print 'Uploading file...'
            status, response = request.next_chunk()
            if response is not None:
                if 'id' in response:
                    print 'Video id "%s" was successfully uploaded.' % response['id']
                else:
                    exit('The upload failed with an unexpected response: %s' % response)
        except HttpError, e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = 'A retriable HTTP error %d occurred:\n%s' % (e.resp.status, e.content)
            else:
                raise
        except RETRIABLE_EXCEPTIONS, e:
            error = 'A retriable error occurred: %s' % e

        if error is not None:
            print error
            retry += 1
            if retry > MAX_RETRIES:
                exit('No longer attempting to retry.')

            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            print 'Sleeping %f seconds and then retrying...' % sleep_seconds
            time.sleep(sleep_seconds)


def get_latest_podcasts():
    podcasts = list()

    last = None
    if os.path.exists(LAST_PODCAST_FILE):
        with open(LAST_PODCAST_FILE, 'r') as f:
            last = f.read()

    d = feedparser.parse(FEED_URL)
    for entry in d['entries']:
        if entry['id'] != last:
            url = None
            for link in entry['links']:
                if link['type'] == 'audio/mpeg':
                    url = link['href']
                    break
            if url is not None:
                podcast = Podcast(title=entry['title'], description=entry['subtitle'], url=url)
                podcasts.append(podcast)
        else:
            break

    last = d['entries'][0]['id']
    with open(LAST_PODCAST_FILE, 'w') as f:
        f.write(last)

    if podcasts:
        print 'Found %s new podcasts.' % str(len(podcasts))
    else:
        print 'Nothing new here. Last podcast uploaded to YouTube was %s' % last

    return podcasts


def download_podcasts(podcasts):
    for podcast in podcasts:
        podcast.filename = podcast.url.split('/')[-1]
        podcast.audio_file = os.path.join(AUDIOS_DIR, podcast.filename)
        response = requests.get(podcast.url, stream=True)
        print 'Downloading file %s...' % podcast.filename
        with open(podcast.audio_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
    return podcasts


def convert_to_flv(podcasts):
    for podcast in podcasts:
        basename = podcast.filename.split('.')[0]
        podcast.video_file = os.path.join(VIDEOS_DIR, '%s.flv' % basename)
        print 'Converting file %s to FLV...' % podcast.filename
        subprocess.call([
            'ffmpeg',
            '-r',
            '1',
            '-loop',
            '1',
            '-i',
            BACKGROUND_IMAGE,
            '-i',
            podcast.audio_file,
            '-acodec',
            'copy',
            '-r',
            '1',
            '-shortest',
            '-vf',
            'scale=1280:720',
            podcast.video_file
        ])
    return podcasts


def upload_to_youtube(podcasts):
    youtube = get_authenticated_service()
    try:
        for podcast in podcasts:
            initialize_upload(youtube, podcast)
    except HttpError, e:
        print 'An HTTP error %d occurred:\n%s' % (e.resp.status, e.content)


def cleanup(podcasts):
    print 'Cleaning up...'
    for podcast in podcasts:
        os.remove(podcast.audio_file)
        os.remove(podcast.video_file)


if __name__ == '__main__':
    podcasts = get_latest_podcasts()
    if podcasts:
        podcasts = download_podcasts(podcasts)
        podcasts = convert_to_flv(podcasts)
        upload_to_youtube(podcasts)
        cleanup(podcasts)
        print 'Process completed!'
