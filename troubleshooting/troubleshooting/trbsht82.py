from constructs import Construct

from aws_cdk import (
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    lambda_layer_kubectl_v28 as kubectlV28,
)


class Trbsht82(Construct):

    def __init__(
        self, scope: Construct, id: str, caller_user_for_mapping: iam.User, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create VPC for the EKS Cluster
        # Default CIDR : 10.0.0.0/16
        self._vpc = ec2.Vpc(
            self,
            id="trbsht-vpc-82",
            vpc_name="trbsht-vpc-82",
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=27
                ),
                ec2.SubnetConfiguration(
                    name="private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=27,
                ),
            ],
        )

        # Create an EKS Cluster
        _cidrs = ["0.0.0.0/0"]
        _endpoint_access = eks.EndpointAccess.PUBLIC_AND_PRIVATE.only_from(*_cidrs)
        self._eks = eks.Cluster(
            self,
            id,
            vpc=self._vpc,
            cluster_name=id,
            version=eks.KubernetesVersion.V1_28,
            default_capacity=0,
            kubectl_layer=kubectlV28.KubectlV28Layer(self, "kubectl"),
            endpoint_access=_endpoint_access,
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
            "trbsht-nodegroup-82",
            nodegroup_name="trbsht-nodegroup-82",
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            instance_types=[
                ec2.InstanceType("t3.large"),
                ec2.InstanceType("t2.medium"),
            ],
            min_size=2,
            node_role=_node_role,
            labels={"system-nodegroup": "true"},
        )
        eks.KubernetesManifest(
            self,
            id="vpcCNI",
            cluster=self._eks,
            overwrite=True,
            manifest=[
                {
                    "apiVersion": "apps/v1",
                    "kind": "DaemonSet",
                    "metadata": {
                        "annotations": {
                            "deprecated.daemonset.template.generation": "1"
                        },
                        "labels": {
                            "app.kubernetes.io/instance": "aws-vpc-cni",
                            "app.kubernetes.io/managed-by": "Helm",
                            "app.kubernetes.io/name": "aws-node",
                            "app.kubernetes.io/version": "v1.15.1",
                            "helm.sh/chart": "aws-vpc-cni-1.15.1",
                            "k8s-app": "aws-node",
                        },
                        "name": "aws-node",
                        "namespace": "kube-system",
                    },
                    "spec": {
                        "revisionHistoryLimit": 10,
                        "selector": {"matchLabels": {"k8s-app": "aws-node"}},
                        "template": {
                            "metadata": {
                                "labels": {
                                    "app.kubernetes.io/instance": "aws-vpc-cni",
                                    "app.kubernetes.io/name": "aws-node",
                                    "k8s-app": "aws-node",
                                },
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
                                                            "key": "eks.amazonaws.com/compute-type",
                                                            "operator": "NotIn",
                                                            "values": ["fargate"],
                                                        },
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                                },
                                "containers": [
                                    {
                                        "env": [
                                            {
                                                "name": "ADDITIONAL_ENI_TAGS",
                                                "value": "{}",
                                            },
                                            {
                                                "name": "ANNOTATE_POD_IP",
                                                "value": "false",
                                            },
                                            {
                                                "name": "AWS_VPC_CNI_NODE_PORT_SUPPORT",
                                                "value": "true",
                                            },
                                            {
                                                "name": "AWS_VPC_ENI_MTU",
                                                "value": "9001",
                                            },
                                            {
                                                "name": "AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG",
                                                "value": "false",
                                            },
                                            {
                                                "name": "AWS_VPC_K8S_CNI_EXTERNALSNAT",
                                                "value": "false",
                                            },
                                            {
                                                "name": "AWS_VPC_K8S_CNI_LOGLEVEL",
                                                "value": "DEBUG",
                                            },
                                            {
                                                "name": "AWS_VPC_K8S_CNI_LOG_FILE",
                                                "value": "/host/var/log/aws-routed-eni/ipamd.log",
                                            },
                                            {
                                                "name": "AWS_VPC_K8S_CNI_RANDOMIZESNAT",
                                                "value": "prng",
                                            },
                                            {
                                                "name": "AWS_VPC_K8S_CNI_VETHPREFIX",
                                                "value": "eni",
                                            },
                                            {
                                                "name": "AWS_VPC_K8S_PLUGIN_LOG_FILE",
                                                "value": "/var/log/aws-routed-eni/plugin.log",
                                            },
                                            {
                                                "name": "AWS_VPC_K8S_PLUGIN_LOG_LEVEL",
                                                "value": "DEBUG",
                                            },
                                            {
                                                "name": "CLUSTER_NAME",
                                                "value": "trbsht-cluster-82",
                                            },
                                            {
                                                "name": "DISABLE_INTROSPECTION",
                                                "value": "false",
                                            },
                                            {
                                                "name": "DISABLE_METRICS",
                                                "value": "false",
                                            },
                                            {
                                                "name": "DISABLE_NETWORK_RESOURCE_PROVISIONING",
                                                "value": "false",
                                            },
                                            {"name": "ENABLE_IPv4", "value": "true"},
                                            {"name": "ENABLE_IPv6", "value": "false"},
                                            {
                                                "name": "ENABLE_POD_ENI",
                                                "value": "false",
                                            },
                                            {
                                                "name": "ENABLE_PREFIX_DELEGATION",
                                                "value": "false",
                                            },
                                            {
                                                "name": "VPC_CNI_VERSION",
                                                "value": "v1.15.1",
                                            },
                                            {
                                                "name": "VPC_ID",
                                                "value": "vpc-08aa789d757be9ec6",
                                            },
                                            {"name": "WARM_ENI_TARGET", "value": "2"},
                                            {
                                                "name": "WARM_PREFIX_TARGET",
                                                "value": "1",
                                            },
                                            {
                                                "name": "MY_NODE_NAME",
                                                "valueFrom": {
                                                    "fieldRef": {
                                                        "apiVersion": "v1",
                                                        "fieldPath": "spec.nodeName",
                                                    }
                                                },
                                            },
                                            {
                                                "name": "MY_POD_NAME",
                                                "valueFrom": {
                                                    "fieldRef": {
                                                        "apiVersion": "v1",
                                                        "fieldPath": "metadata.name",
                                                    }
                                                },
                                            },
                                        ],
                                        "image": "602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/amazon-k8s-cni:v1.15.1-eksbuild.1",
                                        "imagePullPolicy": "IfNotPresent",
                                        "livenessProbe": {
                                            "exec": {
                                                "command": [
                                                    "/app/grpc-health-probe",
                                                    "-addr=:50051",
                                                    "-connect-timeout=5s",
                                                    "-rpc-timeout=5s",
                                                ]
                                            },
                                            "failureThreshold": 3,
                                            "initialDelaySeconds": 60,
                                            "periodSeconds": 10,
                                            "successThreshold": 1,
                                            "timeoutSeconds": 10,
                                        },
                                        "name": "aws-node",
                                        "ports": [
                                            {
                                                "containerPort": 61678,
                                                "name": "metrics",
                                                "protocol": "TCP",
                                            }
                                        ],
                                        "readinessProbe": {
                                            "exec": {
                                                "command": [
                                                    "/app/grpc-health-probe",
                                                    "-addr=:50051",
                                                    "-connect-timeout=5s",
                                                    "-rpc-timeout=5s",
                                                ]
                                            },
                                            "failureThreshold": 3,
                                            "initialDelaySeconds": 1,
                                            "periodSeconds": 10,
                                            "successThreshold": 1,
                                            "timeoutSeconds": 10,
                                        },
                                        "resources": {"requests": {"cpu": "25m"}},
                                        "securityContext": {
                                            "capabilities": {
                                                "add": ["NET_ADMIN", "NET_RAW"]
                                            }
                                        },
                                        "terminationMessagePath": "/dev/termination-log",
                                        "terminationMessagePolicy": "File",
                                        "volumeMounts": [
                                            {
                                                "mountPath": "/host/opt/cni/bin",
                                                "name": "cni-bin-dir",
                                            },
                                            {
                                                "mountPath": "/host/etc/cni/net.d",
                                                "name": "cni-net-dir",
                                            },
                                            {
                                                "mountPath": "/host/var/log/aws-routed-eni",
                                                "name": "log-dir",
                                            },
                                            {
                                                "mountPath": "/var/run/aws-node",
                                                "name": "run-dir",
                                            },
                                            {
                                                "mountPath": "/run/xtables.lock",
                                                "name": "xtables-lock",
                                            },
                                        ],
                                    },
                                    {
                                        "args": [
                                            "--enable-ipv6=false",
                                            "--enable-network-policy=false",
                                            "--enable-cloudwatch-logs=false",
                                            "--enable-policy-event-logs=false",
                                            "--metrics-bind-addr=:8162",
                                            "--health-probe-bind-addr=:8163",
                                        ],
                                        "env": [
                                            {
                                                "name": "MY_NODE_NAME",
                                                "valueFrom": {
                                                    "fieldRef": {
                                                        "apiVersion": "v1",
                                                        "fieldPath": "spec.nodeName",
                                                    }
                                                },
                                            }
                                        ],
                                        "image": "602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/amazon/aws-network-policy-agent:v1.0.4-eksbuild.1",
                                        "imagePullPolicy": "IfNotPresent",
                                        "name": "aws-eks-nodeagent",
                                        "resources": {"requests": {"cpu": "25m"}},
                                        "securityContext": {
                                            "capabilities": {"add": ["NET_ADMIN"]},
                                            "privileged": True,
                                        },
                                        "terminationMessagePath": "/dev/termination-log",
                                        "terminationMessagePolicy": "File",
                                        "volumeMounts": [
                                            {
                                                "mountPath": "/host/opt/cni/bin",
                                                "name": "cni-bin-dir",
                                            },
                                            {
                                                "mountPath": "/sys/fs/bpf",
                                                "name": "bpf-pin-path",
                                            },
                                            {
                                                "mountPath": "/var/log/aws-routed-eni",
                                                "name": "log-dir",
                                            },
                                            {
                                                "mountPath": "/var/run/aws-node",
                                                "name": "run-dir",
                                            },
                                        ],
                                    },
                                ],
                                "dnsPolicy": "ClusterFirst",
                                "hostNetwork": True,
                                "initContainers": [
                                    {
                                        "env": [
                                            {
                                                "name": "DISABLE_TCP_EARLY_DEMUX",
                                                "value": "false",
                                            },
                                            {"name": "ENABLE_IPv6", "value": "false"},
                                        ],
                                        "image": "602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/amazon-k8s-cni-init:v1.15.1-eksbuild.1",
                                        "imagePullPolicy": "IfNotPresent",
                                        "name": "aws-vpc-cni-init",
                                        "resources": {"requests": {"cpu": "25m"}},
                                        "securityContext": {"privileged": True},
                                        "terminationMessagePath": "/dev/termination-log",
                                        "terminationMessagePolicy": "File",
                                        "volumeMounts": [
                                            {
                                                "mountPath": "/host/opt/cni/bin",
                                                "name": "cni-bin-dir",
                                            }
                                        ],
                                    }
                                ],
                                "priorityClassName": "system-node-critical",
                                "restartPolicy": "Always",
                                "schedulerName": "default-scheduler",
                                "serviceAccount": "aws-node",
                                "serviceAccountName": "aws-node",
                                "terminationGracePeriodSeconds": 10,
                                "tolerations": [{"operator": "Exists"}],
                                "volumes": [
                                    {
                                        "hostPath": {"path": "/sys/fs/bpf", "type": ""},
                                        "name": "bpf-pin-path",
                                    },
                                    {
                                        "hostPath": {
                                            "path": "/opt/cni/bin",
                                            "type": "",
                                        },
                                        "name": "cni-bin-dir",
                                    },
                                    {
                                        "hostPath": {
                                            "path": "/etc/cni/net.d",
                                            "type": "",
                                        },
                                        "name": "cni-net-dir",
                                    },
                                    {
                                        "hostPath": {
                                            "path": "/var/log/aws-routed-eni",
                                            "type": "DirectoryOrCreate",
                                        },
                                        "name": "log-dir",
                                    },
                                    {
                                        "hostPath": {
                                            "path": "/var/run/aws-node",
                                            "type": "DirectoryOrCreate",
                                        },
                                        "name": "run-dir",
                                    },
                                    {
                                        "hostPath": {
                                            "path": "/run/xtables.lock",
                                            "type": "",
                                        },
                                        "name": "xtables-lock",
                                    },
                                ],
                            },
                        },
                        "updateStrategy": {
                            "rollingUpdate": {"maxSurge": 0, "maxUnavailable": "10%"},
                            "type": "RollingUpdate",
                        },
                    },
                },
{
  "apiVersion": "apps/v1",
  "kind": "DaemonSet",
  "metadata": {
    "name": "ds-a",
    "namespace": "kube-system",
    "labels": {
      "k8s-app": "ds-a"
    }
  },
  "spec": {
    "selector": {
      "matchLabels": {
        "name": "ds-a"
      }
    },
    "template": {
      "metadata": {
        "labels": {
          "name": "ds-a"
        }
      },
      "spec": {
        "containers": [
          {
            "name": "ds-a",
            "image": "ubuntu",
            "command": [
              "/bin/bash",
              "-ec",
              "while :; do echo '.'; sleep 5 ; done"
            ]
          }
        ]
      }
    }
  }
},
{
  "apiVersion": "apps/v1",
  "kind": "DaemonSet",
  "metadata": {
    "name": "ds-b",
    "namespace": "kube-system",
    "labels": {
      "k8s-app": "ds-b"
    }
  },
  "spec": {
    "selector": {
      "matchLabels": {
        "name": "ds-b"
      }
    },
    "template": {
      "metadata": {
        "labels": {
          "name": "ds-b"
        }
      },
      "spec": {
        "containers": [
          {
            "name": "ds-b",
            "image": "ubuntu",
            "command": [
              "/bin/bash",
              "-ec",
              "while :; do echo '.'; sleep 5 ; done"
            ]
          }
        ]
      }
    }
  }
},{
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "nginx",
                    "namespace": "default",
                    "labels": {"app": "nginx"},
                },
                "spec": {
                    "replicas": 4,
                    "selector": {"matchLabels": {"app": "nginx"}},
                    "template": {
                        "metadata": {"labels": {"app": "nginx"}},
                        "spec": {
                            "containers": [
                                {
                                    "name": "nginx",
                                    "image": "public.ecr.aws/nginx/nginx:stable-perl",
                                    "ports": [{"containerPort": 80}],
                                }
                            ]
                        },
                    },
                },
            }])