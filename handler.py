import json
import os
import sys
import boto3

here = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(here, "./vendored"))

import requests
import time

TOKEN = os.environ['HIPCHAT_TOKEN']
AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
SLEEP_TIME = 10


def get_head():
    client = boto3.client('ecr')
    response = client.list_images(
        repositoryName='airflow',
        maxResults=100,
    )
    tags_list = [i["imageTag"] for i in response["imageIds"] if 'imageTag' in i.keys() and "master" in i["imageTag"]]
    return tags_list[0]


def check_tag(tag):
    client = boto3.client('ecr')
    response = client.list_images(
        repositoryName='airflow',
        maxResults=100,
    )
    tags_list = [i["imageTag"] for i in response["imageIds"] if 'imageTag' in i.keys() and "master" in i["imageTag"]]
    if tag in tags_list:
        return True
    else:
        return False


def aws_deploy(tag):
    client = boto3.client('cloudformation')
    response = client.update_stack(
        StackName='airflow',
        TemplateBody='string',
        TemplateURL='string',
        UsePreviousTemplate=True,
        StackPolicyDuringUpdateBody='string',
        StackPolicyDuringUpdateURL='string',
        Parameters=[
            {
                'ParameterKey': 'AirflowImageTag',
                'ParameterValue': tag,
            },
            {
                'ParameterKey': 'GoogleWebAppClientId',
                'UsePreviousValue': True,
            },
            {
                'ParameterKey': 'AirflowFernetKey',
                'UsePreviousValue': True,
            },
            {
                'ParameterKey': 'GoogleWebAppClientSecret',
                'UsePreviousValue': True,
            },
            {
                'ParameterKey': 'AirflowDBAdminPassword',
                'UsePreviousValue': True,
            },
            {
                'ParameterKey': 'AirflowImageRepo',
                'UsePreviousValue': True,
            },
            {
                'ParameterKey': 'AirflowDBAdminUser',
                'UsePreviousValue': True,
            },
        ],
        Capabilities=[
            'CAPABILITY_NAMED_IAM',
        ],
    )
    time.sleep(5)
    return process


def aws_report_status(room, stack_name="airflow"):
    last_status = ''
    while True:
        client = boto3.client('cloudformation')
        response = client.describe_stacks(
            StackName='airflow',
        )
        status = response['Stacks'][0]['StackStatus']
        if status != last_status:
            status_report = '{stack} Deployment Status: {StackStatus}'.format(
                stack=stack_name.title(),
                StackStatus=process['Stacks'][0]['StackStatus']
            )
            hipchat_notify(room=room,
                           message=status_report,
                           color='gray')
            last_status = status
        if 'COMPLETE' in process['Stacks'][0]['StackStatus'].split('_'):
            return
        time.sleep(SLEEP_TIME)


def hipchat_notify(room,
                   message,
                   color='green',
                   notify=True,
                   format='text',
                   host='api.hipchat.com'):
    if len(message) > 10000:
        raise ValueError('Message too long')
    if format not in ['text', 'html']:
        raise ValueError("Invalid message format '{format}'")
    if color not in ['yellow', 'green', 'red', 'purple', 'gray', 'random']:
        raise ValueError("Invalid color {0}".format(color))
    if not isinstance(notify, bool):
        raise TypeError("Notify must be boolean")
    url = f"https://{host}/v2/room/{room}/notification"
    headers = {'Content-type': 'application/json'}
    headers['Authorization'] = "Bearer " + TOKEN
    payload = {
        'message': message,
        'notify': notify,
        'message_format': format,
        'color': color
    }

    r = requests.post(url, data=json.dumps(payload), headers=headers)
    r.raise_for_status()


def list_tags():
    client = boto3.client('ecr')
    response = client.list_images(
        repositoryName='airflow',
        maxResults=100,
    )
    tags_list = [i["imageTag"] for i in response["imageIds"] if 'imageTag' in i.keys() and "master" in i["imageTag"]]
    tags = ""
    for tag in tags_list:
        tags += tag + "\n"

    return tags


def received(event, context):
    sender_message = json.loads(event['body'])['item']['message']['message']
    sender = json.loads(
        event['body'])['item']['message']['from']['mention_name']
    room = json.loads(event['body'])['item']['room']['name']

    if 'deploy' in sender_message.split(' ')[1] and len(sender_message.split(' ')) > 2:
        branch = get_head()
        if sender_message.split(' ')[2].lower() in ['latest', 'master', 'head']:
            hipchat_notify(room=room,
                           message=f"@{sender} Message received. "
                           "I will deploy latest HEAD branch.")
            aws_deploy(tag=branch)
            aws_report_status(room=room)
        elif check_tag(sender_message.split(' ')[2]):
            branch = sender_message.split(' ')[2]
            hipchat_notify(room=room,
                           message=f"@{sender} Message received. " \
                           f"I will deploy '{sender_message.split(' ')[2]}'" \
                           f" branch.")
            aws_deploy(tag=branch)
            aws_report_status(room=room)
        else:
            hipchat_notify(room=room,
                           message="@{sender} There is no branch named ' \
                           '{branch_name}'.".format(
                            sender=sender,
                            branch_name=sender_message.split(' ')[2]),
                           color="yellow")
    elif sender_message.split(' ')[1] == 'tags':
        hipchat_notify(
            room=room,
            message='@{} \n'.format(sender) + list_tags(),
            color='green'
        )
    elif sender_message.split(' ')[1] == '':
        hipchat_notify(
            room=room,
            message='@{} Hi there.'.format(sender),
            color='green'
        )
    else:
        hipchat_notify(
            room=room,
            message='@{} Sorry I did not understand your message.'.format(
                sender),
            color='red'
        )

    return {
        "statusCode": 200
    }
