import aws_cdk as core
import aws_cdk.assertions as assertions

from part_5_2.part_5_2_stack import Part52Stack

# example tests. To run these tests, uncomment this file along with the example
# resource in part_5_2/part_5_2_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = Part52Stack(app, "part-5-2")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
