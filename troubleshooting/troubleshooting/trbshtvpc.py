from constructs import Construct
import boto3

from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam
)

class TrbshtVpc(Construct):

    @property
    def vpc(self):
        return self._vpc
    
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Create VPC for the EKS Cluster
        # Default CIDR : 10.0.0.0/16
        self._vpc = ec2.Vpc(self, id, vpc_name=id, max_azs=2,subnet_configuration=[
            ec2.SubnetConfiguration(name="public",subnet_type=ec2.SubnetType.PUBLIC),
            ec2.SubnetConfiguration(name="private",subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)])