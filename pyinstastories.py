import threading
import time
import os
import sys
import codecs
import json
import argparse
import datetime

try:
    import urllib.request as urllib
except ImportError:
    import urllib as urllib	

try:
	from instagram_private_api import (
		Client, ClientError, ClientLoginError,
		ClientCookieExpiredError, ClientLoginRequiredError,
		__version__ as client_version)
except ImportError:
	import sys
	sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
	from instagram_private_api import (
		Client, ClientError, ClientLoginError,
		ClientCookieExpiredError, ClientLoginRequiredError,
		__version__ as client_version)

from instagram_private_api import ClientConnectionError
from instagram_private_api import ClientError
from instagram_private_api import ClientThrottledError
from instagram_private_api import Client, ClientCompatPatch

script_version = "1.1"
python_version = sys.version.split(' ')[0]

##Login

def to_json(python_object):
	if isinstance(python_object, bytes):
		return {'__class__': 'bytes',
				'__value__': codecs.encode(python_object, 'base64').decode()}
	raise TypeError(repr(python_object) + ' is not JSON serializable')


def from_json(json_object):
	if '__class__' in json_object and json_object.get('__class__') == 'bytes':
		return codecs.decode(json_object.get('__value__').encode(), 'base64')
	return json_object


def onlogin_callback(api, settings_file):
	cache_settings = api.settings
	with open(settings_file, 'w') as outfile:
		json.dump(cache_settings, outfile, default=to_json)
		print('[I] New auth cookie file was made: {0!s}'.format(settings_file))


def login(username="", password=""):
	device_id = None
	try:
		settings_file = "credentials.json"
		if not os.path.isfile(settings_file):
			# settings file does not exist
			print('[W] Unable to find auth cookie file: {0!s} (creating a new one...)'.format(settings_file))

			# login new
			api = Client(
				username, password,
				on_login=lambda x: onlogin_callback(x, settings_file))
		else:
			with open(settings_file) as file_data:
				cached_settings = json.load(file_data, object_hook=from_json)

			device_id = cached_settings.get('device_id')
			# reuse auth settings
			api = Client(
				username, password,
				settings=cached_settings)

	except (ClientCookieExpiredError, ClientLoginRequiredError) as e:
		print('[E] ClientCookieExpiredError/ClientLoginRequiredError: {0!s}'.format(e))

		# Login expired
		# Do relogin but use default ua, keys and such
		if (username != "" and password != ""):
			api = Client(
				username, password,
				device_id=device_id,
				on_login=lambda x: onlogin_callback(x, settings_file))
		else:
			print("[E] The login cookie has expired, but no login arguments were given.")
			print("[E] Please supply --username and --password arguments.")

	except ClientLoginError as e:
		print('[E] Could not login: {:s}.\n[E] {:s}\n\n{:s}'.format(json.loads(e.error_response).get("error_title", "Error title not available."), json.loads(e.error_response).get("message", "Not available"), e.error_response))
		sys.exit(9)
	except ClientError as e:
		print('[E] Client Error: {0!s}\n[E] Message: {1!s}\n[E] Code: {2:d}\n\n[E] Full response:\n{3!s}\n'.format(e.msg, json.loads(e.error_response).get("message", "Additional error information not available."), e.code, e.error_response))
		sys.exit(9)
	except Exception as e:
		if (str(e).startswith("unsupported pickle protocol")):
			print("[W] This cookie file is not compatible with Python {}.".format(sys.version.split(' ')[0][0]))
			print("[W] Please delete your cookie file 'credentials.json' and try again.")
		else:
			print('[E] Unexpected Exception: {0!s}'.format(e))
		sys.exit(99)

	print('[I] Using cached login cookie for "' + api.authenticated_user_name + '".')
	print('[I] Login to "' + api.authenticated_user_name + '" OK!')
	cookie_expiry = api.cookie_jar.expires_earliest
	print('[I] Login cookie expiry date: {0!s}'.format(datetime.datetime.fromtimestamp(cookie_expiry).strftime('%Y-%m-%d at %I:%M:%S %p')))

	return api




##Downloader

global user_to_check
global ig_client

def check_directories():
	try:
		if not os.path.isdir(os.getcwd() + "/stories/{}/".format(user_to_check)):
			os.makedirs(os.getcwd() + "/stories/{}/".format(user_to_check))
		return True
	except Exception:
		return False


def get_media_story(user_id):
	try:
		print('-' * 50)
		print("Getting stories for user '" + user_to_check + "' ...")
		print('-' * 50)

		try:
			feed = ig_client.user_story_feed(user_id)
		except Exception as e:
			print("An error occurred: " + str(e))
			exit(1)

		try:
			feed_json = feed['reel']['items']
		except TypeError as e:
			print("There are no recent stories to process, skipping ...")
			print('-' * 50)
			print("Story updating ended.")
			print('-' * 50)
			return

		list_video = []
		list_image = []

		list_video_new = []
		list_image_new = []

		for media in feed_json:
			if 'video_versions' in media:
				list_video.append(media['video_versions'][0]['url'])
			else:
				list_image.append(media['image_versions2']['candidates'][0]['url'])

		for video in list_video:
			filename = video.split('/')[-1]
			final_filename = filename.split('.')[0] + ".mp4"
			save_path =  os.getcwd() + "/stories/{}/".format(user_to_check) + final_filename
			if not os.path.exists(save_path):
				print ("[I] Downloading video into " + save_path)
				try:
					urllib.URLopener().retrieve(video, save_path)
					list_video_new.append(save_path)
				except Exception as e:
					print("An error occurred: " + str(e))
					exit(1)
			else:
				print("[I] skipping '" + filename + "' because it already exists")

		for image in list_image:
			filename = (image.split('/')[-1]).split('?', 1)[0]
			final_filename = filename.split('.')[0] + ".jpg"
			save_path = os.getcwd() + "/stories/{}/".format(user_to_check) + final_filename
			if not os.path.exists(save_path):
				print ("[I] Downloading image into " + save_path)
				try:
					urllib.URLopener().retrieve(image, save_path)
					list_image_new.append(save_path)
				except Exception as e:
					print("An error occurred: " + str(e))
					exit(1)
			else:
				print("[I] skipping '" + filename + "' because it already exists")

		if (len(list_image_new) != 0) or (len(list_video_new) != 0):
			print('-' * 50)
			print("[I] Story downloading ended with " + str(len(list_image_new)) + " new images and " + str(len(list_video_new)) + " new videos downloaded.")
			print('-' * 50)
		else:
			print('-' * 50)
			print("Story downloading ended with no new media found.")
			print('-' * 50)
		exit(0)
	except Exception as e:
		print("[E] An error occurred: " + str(e))
		exit(1)
	except KeyboardInterrupt as e:
		print("[I] User aborted download.")
		exit(1)		


print("-" * 70)
print('PYINSTASTORIES (SCRIPT V{:s} - PYTHON V{:s}) - {:s}'.format(script_version, python_version, time.strftime('%I:%M:%S %p')))
print("-" * 70)

parser = argparse.ArgumentParser()
parser.add_argument('-u', '--username', dest='username', type=str, required=False, help="Instagram username to login with.")
parser.add_argument('-p', '--password', dest='password', type=str, required=False, help="Instagram password to login with.")
parser.add_argument('-d', '--download', dest='download', type=str, required=True, help="Instagram user to download stories from.")

# Workaround to 'disable' argument abbreviations
parser.add_argument('--usernamx', help=argparse.SUPPRESS, metavar='IGNORE')
parser.add_argument('--passworx', help=argparse.SUPPRESS, metavar='IGNORE')
parser.add_argument('--downloax', help=argparse.SUPPRESS, metavar='IGNORE')

args, unknown = parser.parse_known_args()

if (args.username and args.password and args.download):
	user_to_check = args.download
	ig_client = login(args.username, args.password)
else:
	settings_file = "credentials.json"
	if not os.path.isfile(settings_file):
		print("[E] No username/password provided, but there is no login cookie present either.")
		print("[E] Please supply --username and --password arguments.")
		exit(1)
	else:
		user_to_check = args.download
		ig_client = login()


if check_directories():
	try:
		user_res = ig_client.username_info(args.download)
		user_id = user_res['user']['pk']
		get_media_story(user_id)
	except Exception as e:
		print("[E] An error occurred: " + str(e))
else:
	print("[E] Could not make required directories.\nPlease create a 'stories' folder manually.")
	exit(1)
