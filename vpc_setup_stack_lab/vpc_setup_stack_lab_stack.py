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

        # Step 1: Creating VPC with public and private subnets
        vpc = ec2.Vpc(self, "MyVpc",
                    #   to handle  multiple AZs,
                       max_azs=3,  # Max Availability Zones
                      nat_gateways=1,  # 1 NAT Gateway
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
                          ),
                      ])

        # Step 2: Creating a Bastion Host Security Group (inbound only from my PC)
        bastion_sg = ec2.SecurityGroup(self, "BastionSG", vpc=vpc,
                                       description="Security group for Bastion host")
        owner_ip=constants.MY_IP
        bastion_sg.add_ingress_rule(ec2.Peer.ipv4(f"{owner_ip}/32"), ec2.Port.tcp(22), "Allow SSH from my IP")

        # Step 3: Creating Frontend Security Group (inbound from anywhere, outbound to Backend)
        frontend_sg = ec2.SecurityGroup(self, "FrontendSG", vpc=vpc,
                                        description="Security group for Frontend")
        frontend_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "Allow HTTP from anywhere")
        frontend_sg.add_egress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(8080), "Allow outbound to Backend")

        # Step 4: Creating Backend Security Group (inbound from Frontend only)
        backend_sg = ec2.SecurityGroup(self, "BackendSG", vpc=vpc,
                                       description="Security group for Backend")
        backend_sg.add_ingress_rule(frontend_sg, ec2.Port.tcp(8080), "Allow inbound from Frontend")
       
        backend_sg.add_egress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "Allow outbound HTTPS")
        # the  above is required inorder to allow the backend to access the internet for external services

        # Step 5: Creating Bastion Host EC2 instance (in Public Subnet)
        bastion_instance = ec2.Instance(self, "BastionInstance",
                                        instance_type=ec2.InstanceType("t2.micro"),
                                        machine_image=ec2.MachineImage.latest_amazon_linux(),
                                        vpc=vpc,
                                        security_group=bastion_sg,
                                        vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
                                        key_name=constants.MY_SSH_KEY_NAME) 

        # Allocating Elastic IP and associating with the Bastion instance
        eip_bastion = ec2.CfnEIP(self, "BastionEIP")
        ec2.CfnEIPAssociation(self, "BastionEIPAssociation", 
                            instance_id=bastion_instance.instance_id, 
                            eip=eip_bastion.ref)

                                        

        # Step 6: Creating Frontend EC2 instance (in Public Subnet)
        frontend_instance = ec2.Instance(self, "FrontendInstance",
                                         instance_type=ec2.InstanceType("t2.micro"),
                                         machine_image=ec2.MachineImage.latest_amazon_linux(),
                                         vpc=vpc,
                                         security_group=frontend_sg,
                                         vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
                                         key_name=constants.MY_SSH_KEY_NAME)  

        # Allocating Elastic IP and associating with the Frontend instance
        eip_frontend = ec2.CfnEIP(self, "FrontendEIP")
        ec2.CfnEIPAssociation(self, "FrontendEIPAssociation", 
                            instance_id=frontend_instance.instance_id, 
                            eip=eip_frontend.ref)                                  

        # Step 7: Creating Backend EC2 instance (in Private Subnet)
        backend_instance = ec2.Instance(self, "BackendInstance",
                                        instance_type=ec2.InstanceType("t2.micro"),
                                        machine_image=ec2.MachineImage.latest_amazon_linux(),
                                        vpc=vpc,
                                        security_group=backend_sg,
                                        vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT),
                                        key_name=constants.MY_SSH_KEY_NAME) 
                                        

        # Step 8: Create an S3 Bucket
        s3_bucket = s3.Bucket(self, "MyS3Bucket",
                              versioned=True,  # Enable versioning
                              removal_policy=RemovalPolicy.DESTROY,  # Cleanup bucket when stack is deleted
                              auto_delete_objects=True)  # Automatically delete objects with stack

        # Step 9: Outputs for easy access
        CfnOutput(self, "BastionInstancePublicIP", value=bastion_instance.instance_public_ip, description="Public IP of Bastion Host")
        CfnOutput(self, "FrontendInstancePublicIP", value=frontend_instance.instance_public_ip, description="Public IP of Frontend Instance")
        CfnOutput(self, "BackendInstancePrivateIP", value=backend_instance.instance_private_ip, description="Private IP of Backend Instance")
        CfnOutput(self, "S3BucketName", value=s3_bucket.bucket_name, description="Name of the S3 Bucket")
