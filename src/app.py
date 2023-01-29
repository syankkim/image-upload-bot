import json
from urllib.parse import parse_qs
import urllib.request
from slack_sdk import WebClient
import requests
import boto3
import uuid
from bs4 import BeautifulSoup
import logging

import os
from dotenv import load_dotenv
load_dotenv()
VERIFICATION_TOKEN = os.environ.get('VERIFICATION_TOKEN')
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
SLACK_USER_TOKEN = os.environ.get('SLACK_USER_TOKEN')
BUCKET_NAME = os.environ.get('BUCKET_NAME')
CLOUDFRONT_HOST = os.environ.get('CLOUDFRONT_HOST')
CHANNEL_ID = os.environ.get('CHANNEL_ID')

client = WebClient(token=SLACK_BOT_TOKEN)
tmp_path = '/tmp/' # AWS lambda에는 /tmp 에만 파일작성 가능.

def get_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger
logger = get_logger()

def make_response(message, status_code, headers):
    if headers is None:
        headers = {}
    return {
        'headers': headers,
        'statusCode': status_code,
        'body': {
            'message': message
        }
    }

def response_blocks(file):
    cloudfront_host = CLOUDFRONT_HOST or ''
    name = file['name']
    origin_name = file['origin_name']
    soup_img = BeautifulSoup('<img/>', 'html.parser')
    img_tag = soup_img.img
    img_tag.attrs['src'] = f'{cloudfront_host}{name}'
    img_tag.attrs['width'] = file['width']
    img_tag.attrs['height'] = file['height']

    soup_div = BeautifulSoup('', 'html.parser')
    div_tag = soup_div.new_tag('div')
    div_tag.attrs['class'] = 'lawtalk-is-image'
    div_tag = img_tag.wrap(div_tag)

    img_tag_block = f'```{img_tag}```'
    class_block = f'```{div_tag}```'
    return [
		{
			'type': 'section',
			'text': {
				'type': 'mrkdwn',
				'text': f':white_check_mark: {origin_name}'
			}
		},
		{
			'type': 'section',
			'text': {
				'type': 'mrkdwn',
				'text': img_tag_block
			}
		},
		{
			'type': 'section',
			'text': {
				'type': 'mrkdwn',
				'text': class_block
			}
		},
        {
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "action_id": "plain_text_input-link"
            },
            "label": {
                "type": "plain_text",
                "text": "이미지 링크 추가",
                "emoji": True
            }
        },
        {
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "action_id": "plain_text_input-alt"
            },
            "label": {
                "type": "plain_text",
                "text": "이미지 설명 추가",
                "emoji": True
            }
        },
        {
			"type": "actions",
			"elements": [
				{
					"type": "button",
					"text": {
						"type": "plain_text",
						"text": "Add tags",
						"emoji": True
					},
					"value": "click_me_1",
					"action_id": "actionId-0"
				}
			]
		}
	]

def s3_connection():
    try:
        s3 = boto3.resource('s3')
    except:
        logger.error('FAIL to connecting S3')
        raise Exception('[ERROR] FAIL to connecting S3')
    else:
        return s3

def upload_S3_bucket(plain_name, file_name):
    logger.info(f'[{plain_name}] Uploading...')
    tmpDirFiles = os.listdir('/tmp')
    if plain_name not in tmpDirFiles:
        raise Exception(f'[ERROR] File not found in path "/tmp".: {tmpDirFiles}')

    s3 = s3_connection()
    bucket = s3.Bucket(BUCKET_NAME)
    local_file = tmp_path+plain_name
    upload_file = file_name
    bucket.upload_file(local_file , upload_file)

def get_image_url(file):
    public_url = file['permalink_public']
    response = requests.get(file['permalink_public'])
    if response.status_code != 200:
        raise Exception(f'Failed to access the file using public url: ({public_url})')
    return str(requests.get(file['permalink_public']).content).split('<meta property="og:image" content="')[1].split('">')[0]

def process(body):
    slack_event = body.get('event')
    if slack_event.get('files'):
        client.chat_postMessage(channel=slack_event['channel'], thread_ts=slack_event['ts'], text='업로드 요청중입니다. 기다려주세요! :meow_noddies:')
        files = slack_event['files']
        file_arr = []

        for file in files:
            _file = {}
            try:
                # 파일을 봇과 채널에서 공유
                client.files_sharedPublicURL(token=SLACK_USER_TOKEN, file=file['id'], channels=CHANNEL_ID)
            except Exception as e:
                logger.warn(f'Failed to share file publicly: {e}')
                pass

            try:
                local_file_name = file['name']
                local_file_path = tmp_path + local_file_name
                # 이미지 확장자 확인
                plain_name, ext = os.path.splitext(local_file_name)
                if ext not in ['.jpg', '.png']:
                    raise Exception(f'Invalid extension.: {ext}')

                # tmp에 이미지 저장 : urllib.reqeust.urlretrieve("이미지 주소", "저장 할 파일이름")
                download_url = get_image_url(file)
                urllib.request.urlretrieve(download_url, local_file_path)
                file_name = f'{uuid.uuid4()}'

                # S3 업로드
                upload_S3_bucket(local_file_name, file_name)
            except Exception as e:
                logger.error(f'{local_file_name} fail to uploading.: {e}')
                continue
            else:
                _file = { 'width': file['original_w'], 'height': file['original_h'], 'name': file_name, 'origin_name': local_file_name }
                file_arr.append(_file)

        if len(file_arr) > 0:
            for file in file_arr:
                try:
                    client.chat_postMessage(channel=slack_event['channel'], thread_ts=slack_event['ts'], blocks=response_blocks(file))
                except Exception as e:
                    logger.error(f'{local_file_name} fail to uploading.: {e}')
                    client.chat_postMessage(channel=slack_event['channel'], thread_ts=slack_event['ts'], text='업로드 실패 :smiling_face_with_tear:')
        else:
            client.chat_postMessage(channel=slack_event['channel'], thread_ts=slack_event['ts'], text='업로드된 파일이 없습니다. :smiling_face_with_tear:')
    return make_response('OK', 200, {'X-Slack-No-Retry': 1})

def add_tags(body):
    # 이미지 태그 markdown to html
    img_tag_str = body['message']['blocks'][2]['text']['text'].replace("```", "")
    img_tag_str = img_tag_str.replace('&lt;', '<')
    img_tag_str = img_tag_str.replace('&gt;', '>')
    soup = BeautifulSoup(img_tag_str, 'html.parser')
    img_tag = soup.find('img')
    soup = BeautifulSoup(img_tag_str, 'html.parser')
    _div_tag = soup.find('div')
    div_tag = soup.new_tag('div')
    div_tag.attrs['class'] = _div_tag.attrs['class']

    container = body['container']
    try:
        if img_tag is None:
            raise Exception(f'img tag is not exists.: {img_tag}')

        a_tag = ''
        # 입력한 link값 가져오기
        inputs =  body['state']['values']
        for key, val in inputs.items():
            try:
                if val.get('plain_text_input-alt'):
                    input_obj = val.get('plain_text_input-alt')
                    if input_obj['value']:
                        img_tag.attrs['alt'] = input_obj['value']
                elif val.get('plain_text_input-link'):
                    input_obj = val.get('plain_text_input-link')
                    if input_obj['value']:
                        new_a_tag = soup.new_tag('a')
                        new_a_tag.attrs['href'] = input_obj['value']
                        a_tag = img_tag.wrap(new_a_tag)
                else:
                    raise Exception(f'Not support input action: {val}')
            except Exception as e:
                raise e

        if a_tag != '':
            img_tag = a_tag
            div_tag = a_tag.wrap(div_tag)
        else:
            div_tag = img_tag.wrap(div_tag)

        client.chat_postMessage(channel=container['channel_id'], thread_ts=container['message_ts'], text=f'```{img_tag}```')
        client.chat_postMessage(channel=container['channel_id'], thread_ts=container['message_ts'], text=f'```{div_tag}```')
        return make_response('OK', 200, {'X-Slack-No-Retry': 1})
    except Exception as e:
        logger.error(e)
        client.chat_postMessage(channel=container['channel_id'], thread_ts=container['message_ts'], text='추가 실패 :smiling_face_with_tear:')
        return make_response('Fail to make threads.', 500, {'X-Slack-No-Retry': 1})

def verify_url(body):
    if body.get("challenge"):
        return {'body': body.get("challenge")}

# main function
def lambda_handler(event, context):
    logger.info(f"Received event:\n{event}")
    req_header = event.get('headers')
    req_body = event.get("body")
    if req_header.get('X-Slack-Retry-Num'):
        logger.info('The event already processed')
        return make_response('OK', 200, {'X-Slack-No-Retry': 1})

    if req_body is None:
        logger.error('Request body is None.')
        return make_response('Request body is None', 500, {'X-Slack-No-Retry': 1})

    # 버튼클릭시 encoded body를 받는다.
    if req_header.get('Content-Type') == 'application/x-www-form-urlencoded':
        decoded_body = parse_qs(req_body)
        body = json.loads(decoded_body['payload'][0])
    elif req_header.get('Content-Type') == 'application/json':
        body = json.loads(req_body)
    else:
        body = None
    logger.info(f"Received body:\n{body}")

    if body.get('token') != VERIFICATION_TOKEN:
        logger.error('Unauthorized token.')
        return make_response('Unauthorized token', 401, {'X-Slack-No-Retry': 1})

    event_type = body.get('type')
    if event_type == 'url_verification':
        return verify_url(body)
    elif event_type == 'event_callback':
        if body['event']['channel']:
            channel_id = body['event']['channel']
        elif body['event']['channel_id']:
            channel_id = body['event']['channel_id']
        if channel_id != CHANNEL_ID:
            logger.error('Forbidden.')
            return make_response('Forbidden.', 403, {'X-Slack-No-Retry': 1})
        return process(body)
    elif event_type == 'block_actions':
        return add_tags(body)
    else:
        logger.warn(f'The event handler not found.: {event_type}')
        return make_response('The event handler not found.', 200, {'X-Slack-No-Retry': 1})
