from constructs import Construct

from aws_cdk import (
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    lambda_layer_kubectl_v28 as kubectlV28,
)


class Trbsht92(Construct):

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

        # Update aws-auth for caller user
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
            min_size=2,
            node_role=_node_role,
        )
        
        sg_backend = ec2.SecurityGroup(self, "MySG", vpc=vpc, allow_all_outbound=True)

        alb_controller = eks.AlbController(self, "albController",
                cluster=self._eks, version=eks.AlbControllerVersion.V2_6_2)

        test = eks.KubernetesManifest(
            self,
            id="game2048",
            cluster=self._eks,
            overwrite=True,
            manifest=[
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {"namespace": "default", "name": "deployment-2048"},
                    "spec": {
                        "selector": {
                            "matchLabels": {"app.kubernetes.io/name": "app-2048"}
                        },
                        "replicas": 2,
                        "template": {
                            "metadata": {
                                "labels": {"app.kubernetes.io/name": "app-2048"}
                            },
                            "spec": {
                                "containers": [
                                    {
                                        "image": "public.ecr.aws/l6m2t8p7/docker-2048:latest",
                                        "imagePullPolicy": "Always",
                                        "name": "app-2048",
                                        "ports": [{"containerPort": 80}],
                                    }
                                ]
                            },
                        },
                    },
                },
                {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {"namespace": "default", "name": "service-2048"},
                    "spec": {
                        "ports": [{"port": 80, "targetPort": 80, "protocol": "TCP"}],
                        "type": "NodePort",
                        "selector": {"app.kubernetes.io/name": "app-2048"},
                    },
                },
                {
                    "apiVersion": "networking.k8s.io/v1",
                    "kind": "Ingress",
                    "metadata": {
                        "namespace": "default",
                        "name": "ingress-2048",
                        "annotations": {
                            "alb.ingress.kubernetes.io/scheme": "internet-facing",
                            "alb.ingress.kubernetes.io/target-type": "instance",
                            "alb.ingress.kubernetes.io/security-groups": sg_backend.security_group_id
                        },
                    },
                    "spec": {
                        "ingressClassName": "alb",
                        "rules": [
                            {
                                "http": {
                                    "paths": [
                                        {
                                            "path": "/",
                                            "pathType": "Prefix",
                                            "backend": {
                                                "service": {
                                                    "name": "service-2048",
                                                    "port": {"number": 80},
                                                }
                                            },
                                        }
                                    ]
                                }
                            }
                        ],
                    },
                },
                {
                    "apiVersion": "v1",
                    "data": {
                        "Corefile": ".:53 {\n    errors\n    log\n    health {\n        lameduck 5s\n      }\n    ready\n    kubernetes cluster.local in-addr.arpa ip6.arpa {\n      pods insecure\n      fallthrough in-addr.arpa ip6.arpa\n    }\n    forward . /etc/resolv.conf\n    prometheus :9153\n        cache 30\n    loop\n    reload\n    loadbalance\n}\n"
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
                }
            ],
        ).node.add_dependency(alb_controller)
