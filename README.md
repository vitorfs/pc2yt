# Podcast to YouTube Auto Uploader

A small hack to automatically upload Podcast audios to YouTube. The code is not pretty (and the required setup neither).

Read the instructions bellow carefully (and also check the source code, it's just a few functions).

It probably won't work out-of-the-box -- sorry about that. 

## How it Works

* Watches a Podcast feed for new episodes;
* Convert the episode to a video format using a static background image;
* Push the video to a YouTube channel.

## Why?

If you already have a Podcast setup and wants to make your episodes available on YouTube this script will automate that task. The file conversion is necessary because YouTube doesn't let you upload audio files to their platform.

## Limitations

I basically made it to fit my wife's Podcast needs, where she uses [Wordpress](https://wordpress.org) and [Blubrry](https://www.blubrry.com/) to generate the xml feed. I don't really understand much about podcasting, but I believe the xml feed should be more or less standarized.

The script uses Python 2. 

## Installation

The script might need some tweaks to make it work on your environment. In my case it's running on a Ubuntu VPS.

```
git clone https://github.com/vitorfs/pc2yt.git
```

After that, install the requirements (ideally inside a virtualenv):

```
pip install -r requirements.txt
```

Now install ffmpeg:

```
apt-get install ffmpeg
```

### Setup

Within the same directory as the `pc2yt.py` file, create two empty folders: `audios` and `videos`.

```
mkdir audios videos
```

Then, create a `.env` file with the URL of your Podcast feed:

**.env**

```
FEED_URL=https://example.com/podcast/feed.xml
```

Save a file named `background.png` in the same directory as the `pc2yt.py`. This file will be used to generate the static background of the podcast video.

To send a file from your local machine to a server:

```
scp background.png root@server_ip_address:/path/to/pc2yt_directory/
```

### YouTube API Credentials

Now go to the [Google Cloud Platform Console](https://console.cloud.google.com), optionally create a new project or use an existing one.

Visit the **APIs & Services** page, then **Credentials** and create a new **OAuth client ID**. You may need to fill out the details of the **OAuth consent screen** before generating the credentials.

After you create your new OAuth credentials, click on the **Download JSON** button. 

You will download a file named `client_secret_9999999999-xxxxxxxxxx.apps.googleusercontent.com.json`.

Rename it to just `client_secret.json` instead.

Now save this file to the save directory as the `pc2yt.py` script. If it's on a cloud server, you can send it using `scp`:

```
scp client_secret.json root@server_ip_address:/path/to/pc2yt_directory/
```

## Usage

There's another configuration file, which is a file named `.last`. This file stores the reference to the last podcast converted and uploaded. The reference I use here is the **id** of the podcast entry. In case of podcast using Wordpress/Blubbry setup, an example of this file contents is:

**.last**

```
https://example.com/?p=596
```

To understand what you should put there you should first inspect your feed xml and check what is used as **id**. You can do that using a Python shell:

```
import feedparser

d = feedparser.parse('https://example.com/feed.xml')
d['entries'][0]['id']
```

This file is not mandatory. If you start the script without a `.last` file, it will download, convert and upload **ALL** podcasts in your feed.

So you can either use `.last` file to set a reference point, from what point it will start converting and uploading, or let the script figure it out.

### First Usage

This is important, because of the OAuth, the first time you use it is a little bit different. You also need to tell to *what YouTube channel* should the script upload the files.

First time you are using it, run the command below:

```
python pc2yt.py --noauth_local_webserver
```

When the code reachs the `get_authenticated_service()` function, you will get a notification on the console. It will give you a long URL. Access this URL on a web browser, select which Google account you want to use and what YouTube channel you want to upload the files to. Finally, get the verification code, go back to the console and paste the verification code.

After that you will see the script will create a file named `youtube.dat`. It will now take care of refreshing the token by itself.

## Crontab

This should be the last thing in the configuration. Depends on how frequently you post new episodes, you might want to tune this setting:

```
sudo crontab -e
```

An example where the script would be execute every hour, at 12:05, 13:05, 14:05, etc:

```
# m h  dom mon dow   command
5 * * * * /home/pc2yt/venv/bin/python /home/pc2yt/pc2yt.py
```
