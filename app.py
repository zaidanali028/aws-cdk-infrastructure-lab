import aws_cdk as cdk

from vpc_setup_stack_lab.vpc_setup_stack_lab_stack import VpcSetupStack

app = cdk.App()
VpcSetupStack(app, "VpcSetupStack",)

app.synth()