from constructs import Construct

from aws_cdk import (
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    lambda_layer_kubectl_v28 as kubectlV28
)


class Trbsht63(Construct):
    
    def __init__(self, scope: Construct, id: str, vpc: ec2.Vpc, caller_user_for_mapping: iam.User, **kwargs):
        super().__init__(scope, id, **kwargs)

        eks_sg = ec2.SecurityGroup(self, "eks cluster SG", vpc=vpc, allow_all_outbound=True)
        eks_sg.add_ingress_rule(eks_sg, ec2.Port.all_tcp(), "All Ports")
    
        # Create an EKS Cluster
        _cidrs = ['0.0.0.0/0']
        _endpoint_access = eks.EndpointAccess.PUBLIC_AND_PRIVATE.only_from(*_cidrs)
        self._eks = eks.Cluster(self, id, vpc=vpc, cluster_name=id, version=eks.KubernetesVersion.V1_28,default_capacity=0, kubectl_layer=kubectlV28.KubectlV28Layer(self, "kubectl"), cluster_logging=[eks.ClusterLoggingTypes.AUTHENTICATOR, eks.ClusterLoggingTypes.AUDIT, eks.ClusterLoggingTypes.CONTROLLER_MANAGER],security_group=eks_sg, endpoint_access=_endpoint_access)
        
        # Update aws-auth for caller user and bastion role
        self._eks.aws_auth.add_user_mapping(user=caller_user_for_mapping, groups=["system:masters"])
          
        # Create LT
        ngrp_lt = ec2.CfnLaunchTemplate(self, "trbsht-ngrp-lt-63",launch_template_name="trbsht-ngrp-lt-63",
                                         launch_template_data=ec2.CfnLaunchTemplate.LaunchTemplateDataProperty(image_id="ami-048f188129fbbcc9f", block_device_mappings=[ec2.CfnLaunchTemplate.BlockDeviceMappingProperty(device_name="/dev/xvda",ebs=ec2.CfnLaunchTemplate.EbsProperty(delete_on_termination=True,volume_size=20,volume_type="gp3"))]))
        
        # Create Node Role
        node_role = iam.Role(self, "nodeRole", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"))
        node_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSWorkerNodePolicy"))
        node_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"))
        node_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKS_CNI_Policy"))
        node_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))
        node_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"))
        
        # Create Node Group
        self._eks.add_nodegroup_capacity("trbsht-nodegroup",
            nodegroup_name="trbsht-nodegroup",
            instance_types=[ec2.InstanceType("t3.large"),ec2.InstanceType("t2.medium")],
            min_size=1,
            node_role=node_role,
            launch_template_spec=eks.LaunchTemplateSpec(id=ngrp_lt.ref, version=ngrp_lt.attr_latest_version_number))