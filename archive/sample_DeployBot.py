#!/usr/bin/env python
"""
This is a demonstration of a bot deploying to airflow repo.
"""

from __future__ import print_function
import requests
import json
import time
import iso8601
import datetime
import os

SLEEP_TIME = 2
ROOMS = ['Room Name']
HIPCHAT_TOKEN = 'Your Token'


class DeployBot(object):
    def __init__(self,
                 sleepTime,
                 rooms,
                 hipchat_token
                 ):
        self.sleepTime = sleepTime
        self.rooms = rooms
        self.hipchat_token = hipchat_token

    def get_head(self):
        bashCommand = "export AWS_PROFILE=chatbot && aws ecr list-images --page-size 100 --repository-name airflow | grep imageTag | tail -n 1"
        process = os.popen(bashCommand).read().split('\n')
        process = [item.replace('"imageTag":','').replace('"','').strip() for item in process ]
        return process

    def check_tag(self, tag):
        bashCommand = f'export AWS_PROFILE=chatbot && aws ecr list-images  ' \
                      f'--repository-name airflow | grep imageTag | grep {tag}'
        process = os.popen(bashCommand).read().replace('"','').replace('imageTag: ','')
        if process:
            return True
        else:
            return False

    def list_tags(self):
        bashCommand = f'export AWS_PROFILE=chatbot && aws ecr list-images  ' \
                      f'--repository-name airflow | grep imageTag | grep _master'
        process = os.popen(bashCommand).read().replace('"','').replace('imageTag: ','')
        return process

    def aws_deploy(self, tag):
        bashCommand = "export AWS_PROFILE=chatbot && aws cloudformation update-stack " \
                      "--stack-name airflow " \
                      "--parameters ParameterKey=AirflowImageTag,ParameterValue={} " \
                      "ParameterKey=GoogleWebAppClientId,UsePreviousValue=true " \
                      "ParameterKey=AirflowFernetKey,UsePreviousValue=true " \
                      "ParameterKey=GoogleWebAppClientSecret,UsePreviousValue=true " \
                      "ParameterKey=AirflowDBAdminPassword,UsePreviousValue=true " \
                      "ParameterKey=AirflowImageRepo,UsePreviousValue=true " \
                      "ParameterKey=AirflowDBAdminUser,UsePreviousValue=true " \
                      "--use-previous-template " \
                      "--capabilities CAPABILITY_NAMED_IAM".format(tag)
        process = os.popen(bashCommand)
        time.sleep(10)
        return process

    def aws_report_status(self, room, stack_name = "airflow"):
        last_status = ''
        while True:
            bashCommand = "export AWS_PROFILE=chatbot && " \
                          "aws cloudformation describe-stacks --stack-name {} --max-items 1".format(stack_name)
            process = json.load(os.popen(bashCommand))
            status = process['Stacks'][0]['StackStatus']
            if status != last_status:
                status_report = '{stack} Deployment Status: {StackStatus}'.format(
                    stack = stack_name.title(),
                    StackStatus = process['Stacks'][0]['StackStatus']
                )
                self.hipchat_notify(room=room,
                                    message=status_report,
                                    color = 'gray')
                last_status = status
            if 'COMPLETE' in process['Stacks'][0]['StackStatus'].split('_'):
                return
            time.sleep(self.sleepTime)

    def hipchat_read(self, room, last_message_id, host='api.hipchat.com'):
        if last_message_id:
            url = f"https://{host}/v2/room/{room}/history/latest?not-before={last_message_id}"
        else:
            url = f"https://{host}/v2/room/{room}/history/latest?max-results=1"
        headers = {'Content-type': 'application/json'}
        headers['Authorization'] = "Bearer " + self.hipchat_token
        r = requests.get(url, headers=headers)
        return r

    def hipchat_notify(self, room, message, color='green', notify=True, format='text', host='api.hipchat.com'):
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
        headers['Authorization'] = "Bearer " + self.hipchat_token
        payload = {
            'message': message,
            'notify': notify,
            'message_format': format,
            'color': color
        }

        r = requests.post(url, data=json.dumps(payload), headers=headers)
        r.raise_for_status()

    def run(self):
        while True:
            for room in self.rooms:
                last_message_id = ''
                try:
                    r = self.hipchat_read(room, last_message_id)
                    r_json = r.json()
                    for message in r_json['items']:
                        if '@OpsBot' in message['message'].split(' ')[0] and \
                                'OpsBot' not in message['from']['mention_name']:
                            if 'deploy' in message['message'].split(' ')[1] and len(message['message'].split(' ')) > 2:
                                branch = self.get_head()
                                if message['message'].split(' ')[2].lower() in ['latest', 'master', 'head']:
                                    self.hipchat_notify(room=room,
                                                        message=f"@{message['from']['mention_name']} " \
                                                                f"Message received. I will deploy latest HEAD branch.")
                                    self.aws_deploy(tag=branch)
                                    self.aws_report_status(room = room)
                                    last_message_id = message['id']
                                elif self.check_tag(message['message'].split(' ')[2]):
                                    branch = message['message'].split(' ')[2]
                                    self.hipchat_notify(room=room,
                                                        message=f"@{message['from']['mention_name']} Message received." \
                                                                f" I will deploy '{message['message'].split(' ')[2]}' " \
                                                                f"branch.")
                                    self.aws_deploy(tag=branch)
                                    self.aws_report_status(room = room)
                                    last_message_id = message['id']
                                else:
                                    self.hipchat_notify(room=room,
                                                        message="@{sender} There is no branch named '{branch_name}'."
                                                        .format(sender=message['from']['mention_name'],
                                                                branch_name=message['message'].split(' ')[2]),
                                                        color="yellow"
                                                        )
                                    last_message_id = message['id']
                            elif message['message'].split(' ')[1] == 'tags':
                                self.hipchat_notify(
                                    room=room,
                                    message='@{} \n'.format(message['from']['mention_name'])+self.list_tags(),
                                    color='green'
                                )
                                last_message_id = message['id']
                            elif message['message'].split(' ')[1] == '':
                                self.hipchat_notify(
                                    room=room,
                                    message='@{} Hi there.'
                                        .format(message['from']['mention_name']),
                                    color='green'
                                )
                                last_message_id = message['id']
                            elif message['message'].split(' ')[1] == '':
                                self.hipchat_notify(
                                    room=room,
                                    message='@{} Hi there.'
                                        .format(message['from']['mention_name']),
                                    color='green'
                                )
                                last_message_id = message['id']
                            else:
                                self.hipchat_notify(
                                    room=room,
                                    message='@{} Sorry I did not understand your message.'
                                        .format(message['from']['mention_name']),
                                    color='red'
                                )
                                last_message_id = message['id']
                except Exception as e:
                    exit(e)
            time.sleep(SLEEP_TIME)


# Initializing bot
deploybot = DeployBot(
    sleepTime=SLEEP_TIME,
    rooms=ROOMS,
    hipchat_token=HIPCHAT_TOKEN
)

# Run deploybot
deploybot.run()
