from constructs import Construct

from aws_cdk import (
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    lambda_layer_kubectl_v28 as kubectlV28
)

#5-2, 5-3
class Trbsht52(Construct):
    
    def __init__(self, scope: Construct, id: str, vpc: ec2.Vpc, caller_user_for_mapping: iam.User, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        #Create Bastion server role and policy
        bastion_role = iam.Role(self, "ec2Role", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"))
        bastion_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))
        bastion_role.add_to_policy(
            iam.PolicyStatement(
                effect = iam.Effect.ALLOW,
                actions = [
                    'eks:UpdateClusterConfig',
                    'eks:DescribeCluster'
                ],
                resources = ['*']
            )
        )
        
        #Create a role for Admin user
        admin_role = iam.Role(self, "adminRole", role_name="adminRole", assumed_by=bastion_role)
        admin_role.add_to_policy(
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
        sg_bastion = ec2.SecurityGroup(self, "bastionSG", vpc=vpc, allow_all_outbound=True)
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
        _instance = ec2.Instance(self, "bastionInstance",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T2, ec2.InstanceSize.MICRO),
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
            vpc = vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=sg_bastion,
            role = bastion_role,
            user_data=setup_commands
        )

        eks_sg = ec2.SecurityGroup(self, "eks cluster SG", vpc=vpc, allow_all_outbound=True)
        eks_sg.add_ingress_rule(eks_sg, ec2.Port.all_tcp(), "All Ports")

        # Create an EKS Cluster
        _cidrs = ["0.0.0.0/0"]
        _endpoint_access = eks.EndpointAccess.PUBLIC_AND_PRIVATE.only_from(*_cidrs)

        self._eks = eks.Cluster(
            self,
            id,
            vpc=vpc,
            cluster_name=id,
            version=eks.KubernetesVersion.V1_28,
            default_capacity=0,
            kubectl_layer=kubectlV28.KubectlV28Layer(self, "kubectl"),
            cluster_logging=[eks.ClusterLoggingTypes.AUTHENTICATOR, eks.ClusterLoggingTypes.AUDIT, eks.ClusterLoggingTypes.CONTROLLER_MANAGER],
            security_group=eks_sg,
            endpoint_access=_endpoint_access
        )
        
        # Update aws-auth for caller user and bastion role
        self._eks.aws_auth.add_user_mapping(user=caller_user_for_mapping, groups=["system:masters"])
        self._eks.aws_auth.add_role_mapping(role=bastion_role, groups=["system:masters"])