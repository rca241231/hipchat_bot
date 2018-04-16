## Hipchat Bot

This repo contains all of the specifications to hipchat bot. The bot has the
following functionalities:

+ List all tags in ECR built from Github
+ Check against tags in ECR
+ Deploy a tag to cloudformation
+ Update status

The bot is hosted in AWS Lambda and can be called as often as possible.

In addition, there is also a single node bot that can be ran on local machine in
the archive folder.

+ To run the bot, follow these steps:
```
$ export AWS_ACCESS_KEY_ID=<Your AWS access key>
$ export AWS_SECRET_ACCESS_KEY=<Your AWS secret key>
```
+ To install the requirements:
```
$ pip install -r requirements.txt -t vendored
```
+ After the installation, the bot can be deployed:
```
$ serverless deploy
```
