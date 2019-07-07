import boto3
import botocore
import random
import urllib3
import json
from datetime import datetime

ec2_client = boto3.client('ec2')
asg_client = boto3.client('autoscaling')

FILTER_TAG_KEY = 'Stack'
FILTER_TAG_VALUE = 'zookeeper'

def lambda_handler(event, context):
    if event["detail-type"] == "EC2 Instance-launch Lifecycle Action":
        instance_id = event['detail']['EC2InstanceId']
        LifecycleHookName = event['detail']['LifecycleHookName']
        AutoScalingGroupName = event['detail']['AutoScalingGroupName']

        #subnet_id = get_subnet_id(instance_id)
        subnet_id = 'subnet-0957c6391237d42db'
        log("subnet_id: {} ".format(subnet_id))

        free_enis = get_free_enis(subnet_id)
        log("Free ENIs: {} ".format([eni["NetworkInterfaceId"] for eni in free_enis]))

        if len(free_enis) == 0:
            log("TODO: FAIL...No free ENIs")

        eni_to_attach = random.choice(free_enis)
        eni_id = eni_to_attach["NetworkInterfaceId"]
        log("eni_to_attach: {} ".format(eni_id))
        # TODO: Check if it's really attached
        # eni_attachment = attach_interface(eni_id, instance_id)
        # if not eni_attachment:
        #     complete_lifecycle_action_failure(LifecycleHookName, AutoScalingGroupName, instance_id)

        ebs_volume = get_ebs_volume(eni_id)
        if len(ebs_volume) == 0:
            log("TODO: FAIL...Volume not found")
        log("Free EBS volumes: {}".format(ebs_volume))
        ebs_attachment = attach_ebs(ebs_volume["VolumeId"], instance_id)




def get_ebs_volume(eni_id):
    """
    TODO
    """

    try:
        result = ec2_client.describe_volumes( Filters=[
            {
                "Name": "tag:Inventory",
                "Values": [eni_id]
            },
            {
                "Name": "status",
                "Values": ["available"]
            }
        ])
        ebs_volume = result['Volumes'][0]

    except botocore.exceptions.ClientError as e:
        #log("Error describing the instance {}: {}".format(internal_subnet, e.response['Error']))
        ebs_volume = None

    return ebs_volume

def get_free_enis(internal_subnet):
    """
    Get all free NetworkInterfaces in the internal subnet with the tag.
    """

    try:
        result = ec2_client.describe_network_interfaces( Filters=[
            {
                "Name": "tag:{}".format(FILTER_TAG_KEY),
                "Values": [FILTER_TAG_VALUE]
            },
            {
                "Name": "subnet-id",
                "Values": [internal_subnet]
            },
            {
                "Name": "status",
                "Values": ["available"]
            }
        ])
        free_enis = result['NetworkInterfaces']

    except botocore.exceptions.ClientError as e:
        log("Error describing the instance {}: {}".format(internal_subnet, e.response['Error']))
        free_enis = None

    return free_enis


def get_subnet_id(instance_id):
    try:
        result = ec2_client.describe_instances(InstanceIds=[instance_id])
        vpc_subnet_id = result['Reservations'][0]['Instances'][0]['SubnetId']
        log("Subnet id: {}".format(vpc_subnet_id))

    except botocore.exceptions.ClientError as e:
        log("Error describing the instance {}: {}".format(instance_id, e.response['Error']))
        vpc_subnet_id = None

    return vpc_subnet_id



def attach_interface(network_interface_id, instance_id):
    attachment = None

    if network_interface_id and instance_id:
        try:
            attach_interface = ec2_client.attach_network_interface(
                NetworkInterfaceId=network_interface_id,
                InstanceId=instance_id,
                DeviceIndex=1
            )
            attachment = attach_interface['AttachmentId']
            log("Created network attachment: {}".format(attachment))
        except botocore.exceptions.ClientError as e:
            log("Error attaching network interface: {}".format(e.response['Error']))

    return attachment

def attach_ebs(ebs_id, instance_id):
    attachment = None

    if ebs_id and instance_id:
        try:
            attach_ebs = ec2_client.attach_volume(
                VolumeId=instance_id,
                InstanceId=instance_id,
                DeviceIndex=1
            )
            attachment = attach_ebs['AttachmentId']
            log("Created ebs attachment: {}".format(attachment))
        except botocore.exceptions.ClientError as e:
            log("Error attaching network interface: {}".format(e.response['Error']))

    return attachment

def complete_lifecycle_action_success(hookname, groupname, instance_id):
    try:
        asg_client.complete_lifecycle_action(
            LifecycleHookName=hookname,
            AutoScalingGroupName=groupname,
            InstanceId=instance_id,
            LifecycleActionResult='CONTINUE'
        )
        log("Lifecycle hook CONTINUEd for: {}".format(instance_id))
    except botocore.exceptions.ClientError as e:
        log("Error completing life cycle hook for instance {}: {}".format(instance_id, e.response['Error']))
        log('{"Error": "1"}')


def complete_lifecycle_action_failure(hookname, groupname, instance_id):
    try:
        asg_client.complete_lifecycle_action(
            LifecycleHookName=hookname,
            AutoScalingGroupName=groupname,
            InstanceId=instance_id,
            LifecycleActionResult='ABANDON'
        )
        log("Lifecycle hook ABANDONed for: {}".format(instance_id))
    except botocore.exceptions.ClientError as e:
        log("Error completing life cycle hook for instance {}: {}".format(instance_id, e.response['Error']))
        log('{"Error": "1"}')


def log(error):
    print('{}Z {}'.format(datetime.utcnow().isoformat(), error))
