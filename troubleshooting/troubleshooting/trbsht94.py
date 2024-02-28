from constructs import Construct
import boto3
from aws_cdk import (
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    Size,
    lambda_layer_kubectl_v28 as kubectlV28,
)


class Trbsht94(Construct):

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.Vpc,
        caller_user_for_mapping: iam.User,
        **kwargs,
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

        if not self._eks.open_id_connect_provider.open_id_connect_provider_arn:
            eks.OpenIdConnectProvider(
                self, "Provider", url=self._eks.cluster_open_id_connect_issuer_url
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

        # Create EBS
        self._pvEbs = ec2.Volume(
            self,
            "pv-ebs",
            volume_name="pv-ebs",
            availability_zone="ap-northeast-2a",
            size=Size.gibibytes(20),
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
        #####################################
        # eks_client = boto3.client("eks")
        # res = eks_client.describe_cluster(name=id)
        # oidc_provider_url = res["cluster"]["identity"]["oidc"]["issuer"]

        # csi_role = iam.Role(
        #     self,
        #     "csiRole",
        #     assumed_by=iam.FederatedPrincipal(
        #         federated=self._eks.open_id_connect_provider.open_id_connect_provider_arn,
        #         conditions={
        #             "StringEquals": {
        #                 f'{oidc_provider_url.replace("https://", "")}:sub': "system:serviceaccount:kube-system:ebs-csi-controller-sa"
        #             }
        #         },
        #         assume_role_action="sts:AssumeRoleWithWebIdentity",
        #     ),
        # )

        # csi_role.add_managed_policy(
        #     iam.ManagedPolicy.from_aws_managed_policy_name(
        #         "service-role/AmazonEBSCSIDriverPolicy"
        #     )
        # )

        # cfn_addon = eks.CfnAddon(
        #     self,
        #     "ebscsiaddon",
        #     addon_name="aws-ebs-csi-driver",
        #     cluster_name=id,
        #     addon_version="v1.28.0-eksbuild.1",
        #     preserve_on_delete=False,
        #     service_account_role_arn=csi_role.role_arn,
        # )

        # manifest = eks.KubernetesManifest(
        #     self,
        #     id="csi-test-pods",
        #     cluster=self._eks,
        #     overwrite=True,
        #     manifest=[
        #         {
        #             "apiVersion": "v1",
        #             "kind": "PersistentVolume",
        #             "metadata": {"name": "test-pv"},
        #             "spec": {
        #                 "accessModes": ["ReadWriteOnce"],
        #                 "capacity": {"storage": "5Gi"},
        #                 "csi": {
        #                     "driver": "ebs.csi.aws.com",
        #                     "fsType": "ext4",
        #                     "volumeHandle": self._pvEbs.volume_id,
        #                 },
        #                 "nodeAffinity": {
        #                 "required": {
        #                     "nodeSelectorTerms": [
        #                     {
        #                         "matchExpressions": [
        #                         {
        #                             "key": "topology.ebs.csi.aws.com/zone",
        #                             "operator": "In",
        #                             "values": [
        #                             "ap-northeast-2a"
        #                             ]
        #                         }
        #                         ]
        #                     }
        #                     ]
        #                 }
        #                 }
        #             },
        #         },
        #         {
        #             "apiVersion": "v1",
        #             "kind": "PersistentVolumeClaim",
        #             "metadata": {"name": "ebs-claim"},
        #             "spec": {
        #                 "storageClassName": None,
        #                 "volumeName": "test-pv",
        #                 "accessModes": ["ReadWriteOnce"],
        #                 "resources": {"requests": {"storage": "5Gi"}},
        #             },
        #         },
        #         {
        #             "apiVersion": "v1",
        #             "kind": "Pod",
        #             "metadata": {"name": "app"},
        #             "spec": {
        #                 "containers": [
        #                     {
        #                         "name": "app",
        #                         "image": "centos",
        #                         "command": ["/bin/sh"],
        #                         "args": [
        #                             "-c",
        #                             "while true; do echo $(date -u) >> /data/out.txt; sleep 5; done",
        #                         ],
        #                         "volumeMounts": [
        #                             {"name": "persistent-storage", "mountPath": "/data"}
        #                         ],
        #                     }
        #                 ],
        #                 "volumes": [
        #                     {
        #                         "name": "persistent-storage",
        #                         "persistentVolumeClaim": {"claimName": "ebs-claim"},
        #                     }
        #                 ],
        #             },
        #         },
        #         {
        #             "apiVersion": "apps/v1",
        #             "kind": "Deployment",
        #             "metadata": {
        #                 "annotations": {"deployment.kubernetes.io/revision": "1"},
        #                 "labels": {
        #                     "app.kubernetes.io/component": "csi-driver",
        #                     "app.kubernetes.io/managed-by": "EKS",
        #                     "app.kubernetes.io/name": "aws-ebs-csi-driver",
        #                     "app.kubernetes.io/version": "1.28.0",
        #                 },
        #                 "name": "ebs-csi-controller",
        #                 "namespace": "kube-system",
        #             },
        #             "spec": {
        #                 "progressDeadlineSeconds": 600,
        #                 "replicas": 0,
        #                 "revisionHistoryLimit": 10,
        #                 "selector": {
        #                     "matchLabels": {
        #                         "app": "ebs-csi-controller",
        #                         "app.kubernetes.io/name": "aws-ebs-csi-driver",
        #                     }
        #                 },
        #                 "strategy": {
        #                     "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": 1},
        #                     "type": "RollingUpdate",
        #                 },
        #                 "template": {
        #                     "metadata": {
        #                         "labels": {
        #                             "app": "ebs-csi-controller",
        #                             "app.kubernetes.io/component": "csi-driver",
        #                             "app.kubernetes.io/managed-by": "EKS",
        #                             "app.kubernetes.io/name": "aws-ebs-csi-driver",
        #                             "app.kubernetes.io/version": "1.28.0",
        #                         },
        #                     },
        #                     "spec": {
        #                         "affinity": {
        #                             "nodeAffinity": {
        #                                 "preferredDuringSchedulingIgnoredDuringExecution": [
        #                                     {
        #                                         "preference": {
        #                                             "matchExpressions": [
        #                                                 {
        #                                                     "key": "eks.amazonaws.com/compute-type",
        #                                                     "operator": "NotIn",
        #                                                     "values": ["fargate"],
        #                                                 }
        #                                             ]
        #                                         },
        #                                         "weight": 1,
        #                                     }
        #                                 ]
        #                             },
        #                             "podAntiAffinity": {
        #                                 "preferredDuringSchedulingIgnoredDuringExecution": [
        #                                     {
        #                                         "podAffinityTerm": {
        #                                             "labelSelector": {
        #                                                 "matchExpressions": [
        #                                                     {
        #                                                         "key": "app",
        #                                                         "operator": "In",
        #                                                         "values": [
        #                                                             "ebs-csi-controller"
        #                                                         ],
        #                                                     }
        #                                                 ]
        #                                             },
        #                                             "topologyKey": "kubernetes.io/hostname",
        #                                         },
        #                                         "weight": 100,
        #                                     }
        #                                 ]
        #                             },
        #                         },
        #                         "containers": [
        #                             {
        #                                 "args": [
        #                                     "controller",
        #                                     "--endpoint=$(CSI_ENDPOINT)",
        #                                     "--k8s-tag-cluster-id=trbsht-cluster",
        #                                     "--batching=true",
        #                                     "--logging-format=text",
        #                                     "--user-agent-extra=eks",
        #                                     "--v=2",
        #                                 ],
        #                                 "env": [
        #                                     {
        #                                         "name": "CSI_ENDPOINT",
        #                                         "value": "unix:///var/lib/csi/sockets/pluginproxy/csi.sock",
        #                                     },
        #                                     {
        #                                         "name": "CSI_NODE_NAME",
        #                                         "valueFrom": {
        #                                             "fieldRef": {
        #                                                 "apiVersion": "v1",
        #                                                 "fieldPath": "spec.nodeName",
        #                                             }
        #                                         },
        #                                     },
        #                                     {
        #                                         "name": "AWS_ACCESS_KEY_ID",
        #                                         "valueFrom": {
        #                                             "secretKeyRef": {
        #                                                 "key": "key_id",
        #                                                 "name": "aws-secret",
        #                                                 "optional": True,
        #                                             }
        #                                         },
        #                                     },
        #                                     {
        #                                         "name": "AWS_SECRET_ACCESS_KEY",
        #                                         "valueFrom": {
        #                                             "secretKeyRef": {
        #                                                 "key": "access_key",
        #                                                 "name": "aws-secret",
        #                                                 "optional": True,
        #                                             }
        #                                         },
        #                                     },
        #                                     {
        #                                         "name": "AWS_EC2_ENDPOINT",
        #                                         "valueFrom": {
        #                                             "configMapKeyRef": {
        #                                                 "key": "endpoint",
        #                                                 "name": "aws-meta",
        #                                                 "optional": True,
        #                                             }
        #                                         },
        #                                     },
        #                                     {
        #                                         "name": "AWS_REGION",
        #                                         "value": "ap-northeast-2",
        #                                     },
        #                                 ],
        #                                 "image": "602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/eks/aws-ebs-csi-driver:v1.28.0",
        #                                 "imagePullPolicy": "IfNotPresent",
        #                                 "livenessProbe": {
        #                                     "failureThreshold": 5,
        #                                     "httpGet": {
        #                                         "path": "/healthz",
        #                                         "port": "healthz",
        #                                         "scheme": "HTTP",
        #                                     },
        #                                     "initialDelaySeconds": 10,
        #                                     "periodSeconds": 10,
        #                                     "successThreshold": 1,
        #                                     "timeoutSeconds": 3,
        #                                 },
        #                                 "name": "ebs-plugin",
        #                                 "ports": [
        #                                     {
        #                                         "containerPort": 9808,
        #                                         "name": "healthz",
        #                                         "protocol": "TCP",
        #                                     }
        #                                 ],
        #                                 "readinessProbe": {
        #                                     "failureThreshold": 5,
        #                                     "httpGet": {
        #                                         "path": "/healthz",
        #                                         "port": "healthz",
        #                                         "scheme": "HTTP",
        #                                     },
        #                                     "initialDelaySeconds": 10,
        #                                     "periodSeconds": 10,
        #                                     "successThreshold": 1,
        #                                     "timeoutSeconds": 3,
        #                                 },
        #                                 "resources": {
        #                                     "limits": {"memory": "256Mi"},
        #                                     "requests": {
        #                                         "cpu": "10m",
        #                                         "memory": "40Mi",
        #                                     },
        #                                 },
        #                                 "securityContext": {
        #                                     "allowPrivilegeEscalation": False,
        #                                     "readOnlyRootFilesystem": True,
        #                                 },
        #                                 "terminationMessagePath": "/dev/termination-log",
        #                                 "terminationMessagePolicy": "File",
        #                                 "volumeMounts": [
        #                                     {
        #                                         "mountPath": "/var/lib/csi/sockets/pluginproxy/",
        #                                         "name": "socket-dir",
        #                                     }
        #                                 ],
        #                             },
        #                             {
        #                                 "args": [
        #                                     "--timeout=60s",
        #                                     "--csi-address=$(ADDRESS)",
        #                                     "--v=2",
        #                                     "--feature-gates=Topology=true",
        #                                     "--extra-create-metadata",
        #                                     "--leader-election=true",
        #                                     "--default-fstype=ext4",
        #                                     "--kube-api-qps=20",
        #                                     "--kube-api-burst=100",
        #                                     "--worker-threads=100",
        #                                 ],
        #                                 "env": [
        #                                     {
        #                                         "name": "ADDRESS",
        #                                         "value": "/var/lib/csi/sockets/pluginproxy/csi.sock",
        #                                     }
        #                                 ],
        #                                 "image": "602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/eks/csi-provisioner:v4.0.0-eks-1-29-5",
        #                                 "imagePullPolicy": "IfNotPresent",
        #                                 "name": "csi-provisioner",
        #                                 "resources": {
        #                                     "limits": {"memory": "256Mi"},
        #                                     "requests": {
        #                                         "cpu": "10m",
        #                                         "memory": "40Mi",
        #                                     },
        #                                 },
        #                                 "securityContext": {
        #                                     "allowPrivilegeEscalation": False,
        #                                     "readOnlyRootFilesystem": True,
        #                                 },
        #                                 "terminationMessagePath": "/dev/termination-log",
        #                                 "terminationMessagePolicy": "File",
        #                                 "volumeMounts": [
        #                                     {
        #                                         "mountPath": "/var/lib/csi/sockets/pluginproxy/",
        #                                         "name": "socket-dir",
        #                                     }
        #                                 ],
        #                             },
        #                             {
        #                                 "args": [
        #                                     "--timeout=60s",
        #                                     "--csi-address=$(ADDRESS)",
        #                                     "--v=2",
        #                                     "--leader-election=true",
        #                                     "--kube-api-qps=20",
        #                                     "--kube-api-burst=100",
        #                                     "--worker-threads=100",
        #                                 ],
        #                                 "env": [
        #                                     {
        #                                         "name": "ADDRESS",
        #                                         "value": "/var/lib/csi/sockets/pluginproxy/csi.sock",
        #                                     }
        #                                 ],
        #                                 "image": "602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/eks/csi-attacher:v4.5.0-eks-1-29-5",
        #                                 "imagePullPolicy": "IfNotPresent",
        #                                 "name": "csi-attacher",
        #                                 "resources": {
        #                                     "limits": {"memory": "256Mi"},
        #                                     "requests": {
        #                                         "cpu": "10m",
        #                                         "memory": "40Mi",
        #                                     },
        #                                 },
        #                                 "securityContext": {
        #                                     "allowPrivilegeEscalation": False,
        #                                     "readOnlyRootFilesystem": True,
        #                                 },
        #                                 "terminationMessagePath": "/dev/termination-log",
        #                                 "terminationMessagePolicy": "File",
        #                                 "volumeMounts": [
        #                                     {
        #                                         "mountPath": "/var/lib/csi/sockets/pluginproxy/",
        #                                         "name": "socket-dir",
        #                                     }
        #                                 ],
        #                             },
        #                             {
        #                                 "args": [
        #                                     "--csi-address=$(ADDRESS)",
        #                                     "--leader-election=true",
        #                                     "--extra-create-metadata",
        #                                     "--kube-api-qps=20",
        #                                     "--kube-api-burst=100",
        #                                     "--worker-threads=100",
        #                                 ],
        #                                 "env": [
        #                                     {
        #                                         "name": "ADDRESS",
        #                                         "value": "/var/lib/csi/sockets/pluginproxy/csi.sock",
        #                                     }
        #                                 ],
        #                                 "image": "602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/eks/csi-snapshotter:v7.0.0-eks-1-29-5",
        #                                 "imagePullPolicy": "IfNotPresent",
        #                                 "name": "csi-snapshotter",
        #                                 "resources": {
        #                                     "limits": {"memory": "256Mi"},
        #                                     "requests": {
        #                                         "cpu": "10m",
        #                                         "memory": "40Mi",
        #                                     },
        #                                 },
        #                                 "securityContext": {
        #                                     "allowPrivilegeEscalation": False,
        #                                     "readOnlyRootFilesystem": True,
        #                                 },
        #                                 "terminationMessagePath": "/dev/termination-log",
        #                                 "terminationMessagePolicy": "File",
        #                                 "volumeMounts": [
        #                                     {
        #                                         "mountPath": "/var/lib/csi/sockets/pluginproxy/",
        #                                         "name": "socket-dir",
        #                                     }
        #                                 ],
        #                             },
        #                             {
        #                                 "args": [
        #                                     "--timeout=60s",
        #                                     "--csi-address=$(ADDRESS)",
        #                                     "--v=2",
        #                                     "--handle-volume-inuse-error=false",
        #                                     "--leader-election=true",
        #                                     "--kube-api-qps=20",
        #                                     "--kube-api-burst=100",
        #                                     "--workers=100",
        #                                 ],
        #                                 "env": [
        #                                     {
        #                                         "name": "ADDRESS",
        #                                         "value": "/var/lib/csi/sockets/pluginproxy/csi.sock",
        #                                     }
        #                                 ],
        #                                 "image": "602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/eks/csi-resizer:v1.10.0-eks-1-29-5",
        #                                 "imagePullPolicy": "IfNotPresent",
        #                                 "name": "csi-resizer",
        #                                 "resources": {
        #                                     "limits": {"memory": "256Mi"},
        #                                     "requests": {
        #                                         "cpu": "10m",
        #                                         "memory": "40Mi",
        #                                     },
        #                                 },
        #                                 "securityContext": {
        #                                     "allowPrivilegeEscalation": False,
        #                                     "readOnlyRootFilesystem": True,
        #                                 },
        #                                 "terminationMessagePath": "/dev/termination-log",
        #                                 "terminationMessagePolicy": "File",
        #                                 "volumeMounts": [
        #                                     {
        #                                         "mountPath": "/var/lib/csi/sockets/pluginproxy/",
        #                                         "name": "socket-dir",
        #                                     }
        #                                 ],
        #                             },
        #                             {
        #                                 "args": ["--csi-address=/csi/csi.sock"],
        #                                 "image": "602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/eks/livenessprobe:v2.12.0-eks-1-29-5",
        #                                 "imagePullPolicy": "IfNotPresent",
        #                                 "name": "liveness-probe",
        #                                 "resources": {
        #                                     "limits": {"memory": "256Mi"},
        #                                     "requests": {
        #                                         "cpu": "10m",
        #                                         "memory": "40Mi",
        #                                     },
        #                                 },
        #                                 "securityContext": {
        #                                     "allowPrivilegeEscalation": False,
        #                                     "readOnlyRootFilesystem": True,
        #                                 },
        #                                 "terminationMessagePath": "/dev/termination-log",
        #                                 "terminationMessagePolicy": "File",
        #                                 "volumeMounts": [
        #                                     {"mountPath": "/csi", "name": "socket-dir"}
        #                                 ],
        #                             },
        #                         ],
        #                         "dnsPolicy": "ClusterFirst",
        #                         "nodeSelector": {"kubernetes.io/os": "linux"},
        #                         "priorityClassName": "system-cluster-critical",
        #                         "restartPolicy": "Always",
        #                         "schedulerName": "default-scheduler",
        #                         "securityContext": {
        #                             "fsGroup": 1000,
        #                             "runAsGroup": 1000,
        #                             "runAsNonRoot": True,
        #                             "runAsUser": 1000,
        #                         },
        #                         "serviceAccount": "ebs-csi-controller-sa",
        #                         "serviceAccountName": "ebs-csi-controller-sa",
        #                         "terminationGracePeriodSeconds": 30,
        #                         "tolerations": [
        #                             {"key": "CriticalAddonsOnly", "operator": "Exists"},
        #                             {
        #                                 "effect": "NoExecute",
        #                                 "operator": "Exists",
        #                                 "tolerationSeconds": 300,
        #                             },
        #                         ],
        #                         "volumes": [{"name": "socket-dir"}],
        #                     },
        #                 },
        #             },
        #         },
        #         {
        #             "apiVersion": "policy/v1",
        #             "kind": "PodDisruptionBudget",
        #             "metadata": {
        #                 "labels": {
        #                     "app.kubernetes.io/component": "csi-driver",
        #                     "app.kubernetes.io/managed-by": "EKS",
        #                     "app.kubernetes.io/name": "aws-ebs-csi-driver",
        #                     "app.kubernetes.io/version": "1.28.0",
        #                 },
        #                 "name": "ebs-csi-controller",
        #                 "namespace": "kube-system",
        #             },
        #             "spec": {
        #                 "maxUnavailable": 5,
        #                 "selector": {
        #                     "matchLabels": {
        #                         "app": "ebs-csi-controller",
        #                         "app.kubernetes.io/name": "aws-ebs-csi-driver",
        #                     }
        #                 },
        #             },
        #         },
        #     ],
        # )
        # manifest.node.add_dependency(cfn_addon)