from constructs import Construct
import boto3

from aws_cdk import (
    Stack,
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_cloudformation as cfn,
    lambda_layer_kubectl_v28 as kubectlV28
)
from .trbshtvpc import TrbshtVpc
from .trbsht52 import Trbsht52
from .trbsht62 import Trbsht62
from .trbsht63 import Trbsht63
from .trbsht65 import Trbsht65
from .trbsht72 import Trbsht72
from .trbsht82 import Trbsht82
from .trbsht84 import Trbsht84
from .trbsht92 import Trbsht92
from .trbsht94 import Trbsht94

class TroubleshootingStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get caller ARN
        caller_user_id = boto3.client('sts').get_caller_identity().get('UserId')
        caller_user_arn = boto3.client('sts').get_caller_identity().get('Arn')
        # Import Caller User
        caller_user_for_mapping = iam.User.from_user_arn(self,id=caller_user_id,user_arn=caller_user_arn)
        
        # Create VPC
        trbsht_vpc = TrbshtVpc(self,"trbsht-vpc")
        
        #5-2 / 5-3
        #Trbsht52(self,"trbsht-cluster",vpc=trbsht_vpc.vpc, caller_user_for_mapping=caller_user_for_mapping)
        
        #6-2
        #Trbsht62(self,"trbsht-cluster", vpc=trbsht_vpc.vpc, caller_user_for_mapping=caller_user_for_mapping)
        
        #6-3
        #Trbsht63(self,"trbsht-cluster", vpc=trbsht_vpc.vpc, caller_user_for_mapping=caller_user_for_mapping)
        
        #6-5
        #Trbsht65(self, "trbsht-cluster", vpc=trbsht_vpc.vpc, caller_user_for_mapping=caller_user_for_mapping)
        
        #7-2
        Trbsht72(self, "trbsht-cluster", vpc=trbsht_vpc.vpc, caller_user_for_mapping=caller_user_for_mapping)
        
        #8-2 Will create the VPC in this contstruct
        #Trbsht82(self, "trbsht-cluster", caller_user_for_mapping=caller_user_for_mapping)
        
        #8-4
        #Trbsht84(self, "trbsht-cluster", vpc=trbsht_vpc.vpc, caller_user_for_mapping=caller_user_for_mapping)
        
        #9-2
        #Trbsht92(self, "trbsht-cluster", vpc=trbsht_vpc.vpc, caller_user_for_mapping=caller_user_for_mapping)
        
        #9-4
        #Trbsht94(self, "trbsht-cluster", vpc=trbsht_vpc.vpc, caller_user_for_mapping=caller_user_for_mapping)
        
        