from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_ec2 as ec2,
    RemovalPolicy,
    CfnOutput
)
import constants
from constructs import Construct

class VpcSetupStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Step 1: Creating VPC with Public and Private Subnets
        vpc = self.create_vpc()

        # Step 2: Creating Security Groups
        bastion_sg = self.create_security_group(
            "BastionSG", vpc, "Security group for Bastion host",
            ingress_rules=[(ec2.Peer.ipv4(f"{constants.MY_IP}/32"), ec2.Port.tcp(22), "Allow SSH from my IP")]
        )

        frontend_sg = self.create_security_group(
            "FrontendSG", vpc, "Security group for Frontend",
            ingress_rules=[
                (bastion_sg, ec2.Port.tcp(22), "Allow SSH from Bastion"),
                (ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "Allow HTTP from anywhere")
            ],
            egress_rules=[(backend_sg, ec2.Port.tcp(8080), "Allow outbound to Backend instance only")]
        )


        backend_sg = self.create_security_group(
            "BackendSG", vpc, "Security group for Backend",
            ingress_rules=[
                (frontend_sg, ec2.Port.tcp(8080), "Allow inbound from Frontend"),
                (bastion_sg, ec2.Port.tcp(22), "Allow SSH from Bastion")
            ],
            egress_rules=[(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "Allow outbound HTTPS")]
        )

       
        # Step 3: Creating Instances
        bastion_instance = self.create_instance(
            "BastionInstance", vpc, bastion_sg, "t2.micro", ec2.SubnetType.PUBLIC
        )
        self.associate_elastic_ip("BastionEIP", bastion_instance)

        frontend_instance = self.create_instance(
            "FrontendInstance", vpc, frontend_sg, "t2.micro", ec2.SubnetType.PUBLIC
        )
        self.associate_elastic_ip("FrontendEIP", frontend_instance)

        backend_instance = self.create_instance(
            "BackendInstance", vpc, backend_sg, "t2.micro", ec2.SubnetType.PRIVATE_WITH_NAT
        )

        # Step 4: Creating S3 Bucket
        s3_bucket = self.create_s3_bucket("MyS3Bucket")

        # Step 5: Outputs
        self.create_outputs(bastion_instance, frontend_instance, backend_instance, s3_bucket)

    def create_vpc(self) -> ec2.Vpc:
        return ec2.Vpc(self, "MyVpc",
                       max_azs=3,
                       nat_gateways=1,
                       subnet_configuration=[
                           ec2.SubnetConfiguration(
                               name="PublicSubnet",
                               subnet_type=ec2.SubnetType.PUBLIC,
                               cidr_mask=24
                           ),
                           ec2.SubnetConfiguration(
                               name="PrivateSubnet",
                               subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT,
                               cidr_mask=24
                           )
                       ])

    def create_security_group(self, id: str, vpc: ec2.Vpc, description: str,
                              ingress_rules: list = None, egress_rules: list = None) -> ec2.SecurityGroup:
        sg = ec2.SecurityGroup(self, id, vpc=vpc, description=description)
        if ingress_rules:
            for peer, port, desc in ingress_rules:
                sg.add_ingress_rule(peer or sg, port, desc)
        if egress_rules:
            for peer, port, desc in egress_rules:
                sg.add_egress_rule(peer or sg, port, desc)
        return sg

    def create_instance(self, id: str, vpc: ec2.Vpc, security_group: ec2.SecurityGroup, instance_type: str,
                        subnet_type: ec2.SubnetType) -> ec2.Instance:
        return ec2.Instance(self, id,
                            instance_type=ec2.InstanceType(instance_type),
                            machine_image=ec2.MachineImage.latest_amazon_linux(),
                            vpc=vpc,
                            security_group=security_group,
                            vpc_subnets=ec2.SubnetSelection(subnet_type=subnet_type),
                            key_name=constants.MY_SSH_KEY_NAME)

    def associate_elastic_ip(self, id: str, instance: ec2.Instance) -> None:
        eip = ec2.CfnEIP(self, f"{id}")
        ec2.CfnEIPAssociation(self, f"{id}Association",
                              instance_id=instance.instance_id,
                              eip=eip.ref)

    def create_s3_bucket(self, id: str) -> s3.Bucket:
        return s3.Bucket(self, id,
                         versioned=True,
                         removal_policy=RemovalPolicy.DESTROY,
                         auto_delete_objects=True)

    def create_outputs(self, bastion: ec2.Instance, frontend: ec2.Instance, backend: ec2.Instance, s3_bucket: s3.Bucket) -> None:
        CfnOutput(self, "BastionInstancePublicIP", value=bastion.instance_public_ip, description="Public IP of Bastion Host")
        CfnOutput(self, "FrontendInstancePublicIP", value=frontend.instance_public_ip, description="Public IP of Frontend Instance")
        CfnOutput(self, "BackendInstancePrivateIP", value=backend.instance_private_ip, description="Private IP of Backend Instance")
        CfnOutput(self, "S3BucketName", value=s3_bucket.bucket_name, description="Name of the S3 Bucket")
