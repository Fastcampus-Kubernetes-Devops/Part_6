from constructs import Construct

from aws_cdk import (
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_autoscaling as asg,
    Fn,
    lambda_layer_kubectl_v28 as kubectlV28
)


class Trbsht62(Construct):
    
    def __init__(self, scope: Construct, id: str, vpc: ec2.Vpc, caller_user_for_mapping: iam.User, **kwargs):
        super().__init__(scope, id, **kwargs)
    
        eks_sg = ec2.SecurityGroup(self, "eks cluster SG", vpc=vpc, allow_all_outbound=True)
        eks_sg.add_ingress_rule(eks_sg, ec2.Port.all_tcp(), "All Ports")
        
        # Create an EKS Cluster
        _cidrs = ['0.0.0.0/0']
        _endpoint_access = eks.EndpointAccess.PUBLIC_AND_PRIVATE.only_from(*_cidrs)
        self._eks = eks.Cluster(self, id, vpc=vpc, cluster_name=id, version=eks.KubernetesVersion.V1_28,default_capacity=0, kubectl_layer=kubectlV28.KubectlV28Layer(self, "kubectl"), endpoint_access=_endpoint_access,cluster_logging=[eks.ClusterLoggingTypes.AUTHENTICATOR, eks.ClusterLoggingTypes.AUDIT, eks.ClusterLoggingTypes.CONTROLLER_MANAGER],security_group=eks_sg)
        
        # Update aws-auth for caller user and bastion role
        self._eks.aws_auth.add_user_mapping(user=caller_user_for_mapping, groups=["system:masters"])
        
        # Create Node Role
        node_role = iam.Role(self, "nodeRole", role_name="trbsht-nodeRole", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"))
        node_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSWorkerNodePolicy"))
        node_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))
        node_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"))
        
        # Create a user data
        _user_data = ec2.UserData.for_linux()
        _user_data.add_commands(
            "set -o xtrace", f"/etc/eks/bootstrap.sh {self._eks.cluster_name}"
        )

        # self managed node group
        asg.AutoScalingGroup(self,"selfNgrp",vpc=vpc, auto_scaling_group_name="self-managed-node-group", instance_type=ec2.InstanceType("t3.large"),machine_image=ec2.MachineImage.generic_linux({'ap-northeast-2':'ami-048f188129fbbcc9f'}), min_capacity=1,role=node_role,user_data=_user_data,security_group=eks_sg)