#Par_5_2
from constructs import Construct
import boto3

from aws_cdk import (
    Stack,
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    lambda_layer_kubectl_v28 as kubectlV28
)

class Part52Stack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get caller ARN
        caller_user_id = boto3.client('sts').get_caller_identity().get('UserId')
        caller_user_arn = boto3.client('sts').get_caller_identity().get('Arn')
        
        # Import Caller User
        caller_user_for_mapping = iam.User.from_user_arn(self,id=caller_user_id,user_arn=caller_user_arn)

        # Create PC for the EKS Cluster
        vpc = ec2.Vpc(self, "Part5_2_TrbshtVpc", max_azs=2,
                      subnet_configuration=[
                          ec2.SubnetConfiguration(name="Part5_2_public",subnet_type=ec2.SubnetType.PUBLIC),
                          ec2.SubnetConfiguration(name="Part5_2_private",subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                          ])
        
        #Create Bastion server role and policy
        role = iam.Role(self, "Part5_2_ec2role", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"))
        role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))
        role.add_to_policy(
            iam.PolicyStatement(
                effect = iam.Effect.ALLOW,
                actions = [
                    'eks:UpdateClusterConfig',
                    'eks:DescribeCluster'
                ],
                resources = ['*']
            )
        )
        
        #Create Security Group
        sg_bastion = ec2.SecurityGroup(self, "Part5_2_bastionSG", vpc=vpc, allow_all_outbound=True)
        sg_bastion.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH")
        
        #Install kubectl on bastion instance
        setup_commands = ec2.UserData.for_linux()
        setup_commands.add_commands("sudo curl -O https://s3.us-west-2.amazonaws.com/amazon-eks/1.28.5/2024-01-04/bin/linux/amd64/kubectl",
                                        "sudo chmod +x ./kubectl",
                                        "sudo mkdir -p $HOME/bin && sudo cp ./kubectl $HOME/bin/kubectl && export PATH=$HOME/bin:$PATH",
                                        "sudo echo 'export PATH=$HOME/bin:$PATH' >> ~/.bashrc",
                                        "sudo yum remove awscli",
                                        "sudo curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o 'awscliv2.zip'",
                                        "unzip awscliv2.zip",
                                        "sudo ./aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli --update"
                                        )
        
        #Create bastion instance
        instance = ec2.Instance(self, "Part5_2_bastionInstance",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T2, ec2.InstanceSize.MICRO),
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
            vpc = vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=sg_bastion,
            role = role,
            user_data=setup_commands
        )

        #Restrict Public Access
        cidrs = ['1.2.3.4/32']
        _endpoint_access = eks.EndpointAccess.PUBLIC_AND_PRIVATE.only_from(*cidrs)

        # Create an EKS Cluster
        cluster = eks.Cluster(self, "Part5_2_trbsht-cluster",vpc=vpc,cluster_name="Part5_2_trbsht-cluster",version=eks.KubernetesVersion.V1_28,default_capacity=0,kubectl_layer=kubectlV28.KubectlV28Layer(self, "kubectl"), endpoint_access=_endpoint_access)
        
        # Update aws-auth for caller user
        cluster.aws_auth.add_user_mapping(user=caller_user_for_mapping, groups=["system:masters"])