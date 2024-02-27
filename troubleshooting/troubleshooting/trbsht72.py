from constructs import Construct
from aws_cdk import (
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    lambda_layer_kubectl_v28 as kubectlV28,
)

class Trbsht72(Construct):

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
        _cidrs = ['0.0.0.0/0']
        _endpoint_access = eks.EndpointAccess.PUBLIC_AND_PRIVATE.only_from(*_cidrs)
        self._eks = eks.Cluster(self, id, vpc=vpc, cluster_name=id, version=eks.KubernetesVersion.V1_28,default_capacity=0, kubectl_layer=kubectlV28.KubectlV28Layer(self, "kubectl"), cluster_logging=[eks.ClusterLoggingTypes.AUTHENTICATOR, eks.ClusterLoggingTypes.AUDIT, eks.ClusterLoggingTypes.CONTROLLER_MANAGER],security_group=eks_sg, endpoint_access=_endpoint_access)

        # Update aws-auth for caller user
        self._eks.aws_auth.add_user_mapping(
            user=caller_user_for_mapping, groups=["system:masters"]
        )

        # Create Node Group
        self._eks.add_nodegroup_capacity(
            "trbsht-nodegroup-72",
            nodegroup_name="trbsht-nodegroup-72",
            instance_types=[
                ec2.InstanceType("t3.large"),
                ec2.InstanceType("t2.medium"),
            ],
            min_size=1,
            labels={"system-nodegroup": "true"},
        )

        # Deploy coreDNS
        eks.KubernetesManifest(
            self,
            id="coreDNS",
            cluster=self._eks,
            overwrite=True,
            manifest=[
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {
                        "annotations": {"deployment.kubernetes.io/revision": "1"},
                        "labels": {
                            "eks.amazonaws.com/component": "coredns",
                            "k8s-app": "kube-dns",
                            "kubernetes.io/name": "CoreDNS",
                        },
                        "name": "coredns",
                        "namespace": "kube-system",
                    },
                    "spec": {
                        "progressDeadlineSeconds": 600,
                        "replicas": 2,
                        "revisionHistoryLimit": 10,
                        "selector": {
                            "matchLabels": {
                                "eks.amazonaws.com/component": "coredns",
                                "k8s-app": "kube-dns",
                            }
                        },
                        "strategy": {
                            "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": 1},
                            "type": "RollingUpdate",
                        },
                        "template": {
                            "metadata": {
                                "labels": {
                                    "eks.amazonaws.com/component": "coredns",
                                    "k8s-app": "kube-dns",
                                }
                            },
                            "spec": {
                                "affinity": {
                                    "nodeAffinity": {
                                        "requiredDuringSchedulingIgnoredDuringExecution": {
                                            "nodeSelectorTerms": [
                                                {
                                                    "matchExpressions": [
                                                        {
                                                            "key": "kubernetes.io/os",
                                                            "operator": "In",
                                                            "values": ["linux"],
                                                        },
                                                        {
                                                            "key": "kubernetes.io/arch",
                                                            "operator": "In",
                                                            "values": [
                                                                "amd64",
                                                                "arm64",
                                                            ],
                                                        },
                                                        {
                                                            "key": "system-nodegroup",
                                                            "operator": "In",
                                                            "values": ["true"],
                                                        },
                                                    ]
                                                }
                                            ]
                                        }
                                    },
                                    "podAntiAffinity": {
                                        "preferredDuringSchedulingIgnoredDuringExecution": [
                                            {
                                                "podAffinityTerm": {
                                                    "labelSelector": {
                                                        "matchExpressions": [
                                                            {
                                                                "key": "k8s-app",
                                                                "operator": "In",
                                                                "values": ["kube-dns"],
                                                            }
                                                        ]
                                                    },
                                                    "topologyKey": "kubernetes.io/hostname",
                                                },
                                                "weight": 100,
                                            }
                                        ]
                                    },
                                },
                                "containers": [
                                    {
                                        "args": ["-conf", "/etc/coredns/Corefile"],
                                        "image": "602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/eks/coredns:v1.10.1-eksbuild.4",
                                        "imagePullPolicy": "IfNotPresent",
                                        "livenessProbe": {
                                            "failureThreshold": 5,
                                            "httpGet": {
                                                "path": "/health",
                                                "port": 8080,
                                                "scheme": "HTTP",
                                            },
                                            "initialDelaySeconds": 60,
                                            "periodSeconds": 10,
                                            "successThreshold": 1,
                                            "timeoutSeconds": 5,
                                        },
                                        "name": "coredns",
                                        "ports": [
                                            {
                                                "containerPort": 53,
                                                "name": "dns",
                                                "protocol": "UDP",
                                            },
                                            {
                                                "containerPort": 53,
                                                "name": "dns-tcp",
                                                "protocol": "TCP",
                                            },
                                            {
                                                "containerPort": 9153,
                                                "name": "metrics",
                                                "protocol": "TCP",
                                            },
                                        ],
                                        "readinessProbe": {
                                            "failureThreshold": 3,
                                            "httpGet": {
                                                "path": "/ready",
                                                "port": 8181,
                                                "scheme": "HTTP",
                                            },
                                            "periodSeconds": 10,
                                            "successThreshold": 1,
                                            "timeoutSeconds": 1,
                                        },
                                        "resources": {
                                            "limits": {"memory": "200Mi"},
                                            "requests": {
                                                "cpu": "100m",
                                                "memory": "70Mi",
                                            },
                                        },
                                        "securityContext": {
                                            "allowPrivilegeEscalation": False,
                                            "capabilities": {
                                                "add": ["NET_BIND_SERVICE"],
                                                "drop": ["all"],
                                            },
                                            "readOnlyRootFilesystem": True,
                                        },
                                        "terminationMessagePath": "/dev/termination-log",
                                        "terminationMessagePolicy": "File",
                                        "volumeMounts": [
                                            {
                                                "mountPath": "/etc/coredns",
                                                "name": "config-volume",
                                                "readOnly": False,
                                            },
                                            {"mountPath": "/tmp", "name": "tmp"},
                                        ],
                                    }
                                ],
                                "dnsPolicy": "Default",
                                "priorityClassName": "system-cluster-critical",
                                "restartPolicy": "Always",
                                "schedulerName": "default-scheduler",
                                "serviceAccount": "coredns",
                                "serviceAccountName": "coredns",
                                "terminationGracePeriodSeconds": 30,
                                "tolerations": [
                                    {
                                        "effect": "NoSchedule",
                                        "key": "node-role.kubernetes.io/master",
                                    },
                                    {"key": "CriticalAddonsOnly", "operator": "Exists"},
                                ],
                                "volumes": [
                                    {"name": "tmp"},
                                    {
                                        "configMap": {
                                            "defaultMode": 420,
                                            "items": [
                                                {"key": "Corefile", "path": "Corefile"}
                                            ],
                                            "name": "coredns",
                                        },
                                        "name": "config-volume",
                                    },
                                ],
                            },
                        },
                    },
                }
            ],
        )
