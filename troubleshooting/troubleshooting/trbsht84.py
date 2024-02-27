from constructs import Construct

from aws_cdk import (
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    lambda_layer_kubectl_v28 as kubectlV28,
)


class Trbsht84(Construct):

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.Vpc,
        caller_user_for_mapping: iam.User,
        **kwargs
    ):
        super().__init__(scope, id, **kwargs)
        
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
        self._eks.aws_auth.add_user_mapping(
            user=caller_user_for_mapping, groups=["system:masters"]
        )

        # Create Node Role
        _node_role = iam.Role(
            self, "nodeRole", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com")
        )
        _node_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSWorkerNodePolicy")
        )
        _node_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonEC2ContainerRegistryReadOnly"
            )
        )
        _node_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKS_CNI_Policy")
        )
        _node_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )
        _node_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess")
        )

        # Create Node Group
        self._eks.add_nodegroup_capacity(
            "trbsht-nodegroup",
            nodegroup_name="trbsht-nodegroup",
            instance_types=[
                ec2.InstanceType("t3.large"),
                ec2.InstanceType("t2.medium"),
            ],
            min_size=1,
            node_role=_node_role,
        )
        eks.KubernetesManifest(
            self,
            id="coreDNSCM",
            cluster=self._eks,
            overwrite=True,
            manifest=[
                {
                    "apiVersion": "v1",
                    "data": {
                        "Corefile": ".:53 {\n    errors\n    log\n    health {\n        lameduck 5s\n      }\n    ready\n    kubernetes cluster.local in-addr.arpa ip6.arpa {\n      pods insecure\n      fallthrough in-addr.arpa ip6.arpa\n    }\n    prometheus :9153\n        cache 30\n    loop\n    reload\n    loadbalance\n}\n"
                    },
                    "kind": "ConfigMap",
                    "metadata": {
                        "labels": {
                            "eks.amazonaws.com/component": "coredns",
                            "k8s-app": "kube-dns",
                        },
                        "name": "coredns",
                        "namespace": "kube-system",
                    },
                },
                {
                    "apiVersion": "v1",
                    "kind": "Pod",
                    "metadata": {"name": "nettools"},
                    "spec": {
                        "containers": [
                            {
                                "name": "nettools",
                                "image": "jrecord/nettools:latest",
                                "command": ["sleep", "999999"],
                                "imagePullPolicy": "IfNotPresent",
                            }
                        ],
                        "restartPolicy": "Never",
                        "dnsPolicy": "None",
                        "dnsConfig": {
                            "nameservers": ["4.132.113.222"],
                            "searches": [
                                "ns1.svc.cluster-domain.example",
                                "my.dns.search.suffix",
                            ],
                            "options": [
                                {"name": "ndots", "value": "3"},
                                {"name": "edns0"},
                            ],
                        },
                    },
                },
            ],
        )
