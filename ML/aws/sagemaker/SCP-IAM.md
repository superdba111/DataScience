The main difference between Service Control Policies (SCPs) and IAM policies in the AWS Identity and Access Management (IAM) console is the scope of their permissions.

IAM policies are used to define permissions for individual IAM users, groups, and roles within a single AWS account. IAM policies can be used to grant or deny permissions for specific AWS services and resources, and they can be attached to users, groups, and roles directly or via resource-based policies.

In contrast, SCPs are used to define permissions across multiple AWS accounts in an AWS Organization. SCPs are attached to organizational units (OUs), accounts, or the entire organization, and they are used to restrict or allow access to AWS services and actions across accounts. SCPs can be used to limit the actions that IAM users and roles can take within an account, enforce compliance policies, or apply guardrails to prevent unauthorized access.

Another key difference is that SCPs take precedence over IAM policies. If an SCP is attached to an OU or account that contains an IAM user or role, the SCP takes precedence over any IAM policies that are attached to that user or role. This means that an SCP can be used to limit the permissions of an IAM user or role even if that user or role has an IAM policy that grants more permissive permissions.

Overall, IAM policies are used to manage permissions within a single AWS account, while SCPs are used to manage permissions across multiple accounts in an AWS Organization. SCPs are a powerful tool for enforcing compliance and applying governance policies across your AWS accounts.

Service Control Policies (SCPs) in the IAM console is a feature of AWS Identity and Access Management (IAM) that allows you to manage permissions across multiple AWS accounts in your organization.

SCPs are a type of IAM policy that you can attach to an AWS Organizations entity, such as an organization, organizational unit (OU), or an account, to define the maximum permissions that can be applied to the resources within that entity. SCPs are used to limit permissions across accounts and apply guardrails that enforce compliance policies.

For example, you can use an SCP to prevent IAM users in an AWS account from creating public Amazon S3 buckets or launching EC2 instances with a specific instance type. SCPs can also be used to enforce security policies, such as requiring multi-factor authentication (MFA) for certain actions or restricting access to specific AWS services.

When you attach an SCP to an AWS Organizations entity, the policy affects all IAM users and roles within that entity, as well as any resources created in that entity. SCPs override any permissions that are granted by IAM policies or resource policies, so they can be used to ensure that all IAM users and roles within an entity have the same maximum permissions, regardless of any policies that are applied to individual users or roles.

You can create and manage SCPs from the IAM console. To get started, you need to have AWS Organizations set up for your account, and then you can navigate to the "Service Control Policies" page in the IAM console to create and manage your SCPs.

if you use AWS Control Tower to set up and manage your multi-account AWS environment, then Service Control Policies (SCPs) are automatically created and applied to your accounts.

AWS Control Tower is a service that provides pre-packaged best practices for setting up and governing a secure, compliant, and well-architected multi-account AWS environment. Control Tower automates the creation of a landing zone, which is a secure and well-architected multi-account environment, and sets up the necessary AWS services and configurations to govern your environment.

As part of the landing zone setup process, Control Tower automatically creates a set of default SCPs that are applied to the organizational units (OUs) and accounts in your environment. These SCPs are designed to enforce security and compliance policies, such as restricting access to certain AWS services or requiring multi-factor authentication (MFA) for certain actions.

You can also create custom SCPs in Control Tower to enforce additional policies that are specific to your organization's needs. These custom SCPs can be applied to specific OUs or accounts within your environment to further restrict or allow access to AWS services and actions.

Overall, SCPs are an important tool for managing permissions and enforcing security policies in a multi-account AWS environment, and Control Tower automates the creation and management of SCPs to make it easier to set up and manage a secure and compliant AWS environment.


