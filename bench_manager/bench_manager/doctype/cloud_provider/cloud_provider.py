# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
import boto3
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password


class CloudProvider(Document):
	def validate(self):
		if self.provider_type == "AWS EC2":
			self.validate_aws_credentials()
			self.check_region_change()

	def check_region_change(self):
		"""Detect region change and clear VPC resources to force reprovision"""
		if self.region != self.db_get("region"):
			# Region changed, clear VPC resources
			self.db_set({
				"vpc_id": "",
				"subnet_id": "",
				"security_group_id": "",
				"ssh_key_name": ""
			})
			frappe.msgprint(f"Region changed to {self.region}. VPC will be reprovisioned on next operation.")

	def validate_aws_credentials(self):
		"""Validate AWS credentials by attempting to describe regions"""
		try:
			aws_access_key_id = self.aws_access_key_id
			
			# Use decrypted password if document exists, otherwise use plain text
			if self.name and frappe.db.exists("Cloud Provider", self.name):
				aws_secret_access_key = get_decrypted_password(
					"Cloud Provider", self.name, "aws_secret_access_key"
				)
			else:
				aws_secret_access_key = self.aws_secret_access_key
			
			client = boto3.client(
				"ec2",
				aws_access_key_id=aws_access_key_id,
				aws_secret_access_key=aws_secret_access_key,
				region_name=self.region
			)
			
			# Test credentials by describing regions
			client.describe_regions()
			
		except Exception as e:
			frappe.throw(f"Invalid AWS credentials: {str(e)}")

	def get_aws_client(self, service="ec2"):
		"""Get authenticated AWS client"""
		aws_access_key_id = self.aws_access_key_id
		aws_secret_access_key = get_decrypted_password(
			"Cloud Provider", self.name, "aws_secret_access_key"
		)
		
		return boto3.client(
			service,
			aws_access_key_id=aws_access_key_id,
			aws_secret_access_key=aws_secret_access_key,
			region_name=self.region
		)

	def before_save(self):
		if self.enabled:
			self.status = "Active"
		else:
			self.status = "Inactive"

	@frappe.whitelist()
	def provision_vpc(self):
		"""Provision VPC for the cloud provider"""
		if self.provider_type != "AWS EC2":
			frappe.throw("VPC provisioning is only supported for AWS EC2")
		
		try:
			ec2_client = self.get_aws_client()
			
			# Create VPC
			vpc_response = ec2_client.create_vpc(
				CidrBlock="10.0.0.0/16",
				TagSpecifications=[
					{
						"ResourceType": "vpc",
						"Tags": [
							{"Key": "Name", "Value": f"BenchManager-{self.name}"}
						]
					}
				]
			)
			vpc_id = vpc_response["Vpc"]["VpcId"]
			
			# Create Internet Gateway
			igw_response = ec2_client.create_internet_gateway()
			igw_id = igw_response["InternetGateway"]["InternetGatewayId"]
			
			# Attach Internet Gateway to VPC
			ec2_client.attach_internet_gateway(
				InternetGatewayId=igw_id,
				VpcId=vpc_id
			)
			
			# Create Subnet with public IP enabled
			subnet_response = ec2_client.create_subnet(
				VpcId=vpc_id,
				CidrBlock="10.0.1.0/24",
				MapPublicIpOnLaunch=True,
				TagSpecifications=[
					{
						"ResourceType": "subnet",
						"Tags": [
							{"Key": "Name", "Value": f"BenchManager-{self.name}-subnet"}
						]
					}
				]
			)
			subnet_id = subnet_response["Subnet"]["SubnetId"]
			
			# Create Route Table
			rt_response = ec2_client.create_route_table(
				VpcId=vpc_id,
				TagSpecifications=[
					{
						"ResourceType": "route-table",
						"Tags": [
							{"Key": "Name", "Value": f"BenchManager-{self.name}-rt"}
						]
					}
				]
			)
			rt_id = rt_response["RouteTable"]["RouteTableId"]
			
			# Add route to Internet Gateway
			ec2_client.create_route(
				RouteTableId=rt_id,
				DestinationCidrBlock="0.0.0.0/0",
				GatewayId=igw_id
			)
			
			# Associate subnet with route table
			ec2_client.associate_route_table(
				RouteTableId=rt_id,
				SubnetId=subnet_id
			)
			
			# Create Security Group
			sg_response = ec2_client.create_security_group(
				GroupName=f"BenchManager-{self.name}-sg",
				Description="Security group for Bench Manager",
				VpcId=vpc_id
			)
			sg_id = sg_response["GroupId"]
			
			# Add inbound rules for SSH (22), HTTP (80), HTTPS (443)
			ec2_client.authorize_security_group_ingress(
				GroupId=sg_id,
				IpPermissions=[
					{
						"IpProtocol": "tcp",
						"FromPort": 22,
						"ToPort": 22,
						"IpRanges": [{"CidrIp": "0.0.0.0/0"}]
					},
					{
						"IpProtocol": "tcp",
						"FromPort": 80,
						"ToPort": 80,
						"IpRanges": [{"CidrIp": "0.0.0.0/0"}]
					},
					{
						"IpProtocol": "tcp",
						"FromPort": 443,
						"ToPort": 443,
						"IpRanges": [{"CidrIp": "0.0.0.0/0"}]
					}
				]
			)
			
			# Create SSH Key Pair
			key_response = ec2_client.create_key_pair(
				KeyName=f"BenchManager-{self.name}-key"
			)
			ssh_key_name = key_response["KeyName"]
			
			# Update Cloud Provider with IDs
			self.db_set({
				"vpc_id": vpc_id,
				"subnet_id": subnet_id,
				"security_group_id": sg_id,
				"ssh_key_name": ssh_key_name
			})
			
			return {
				"vpc_id": vpc_id,
				"subnet_id": subnet_id,
				"security_group_id": sg_id,
				"ssh_key_name": ssh_key_name
			}
			
		except Exception as e:
			frappe.throw(f"Failed to provision VPC: {str(e)}")

	@frappe.whitelist()
	def create_ssh_key_pair(self, key_name=None):
		"""Create SSH key pair for the cloud provider"""
		if self.provider_type != "AWS EC2":
			frappe.throw("SSH key creation is only supported for AWS EC2")
		
		try:
			ec2_client = self.get_aws_client()
			
			if not key_name:
				key_name = f"BenchManager-{self.name}-key"
			
			# If key name already exists, append a version suffix
			try:
				ec2_client.describe_key_pairs(KeyNames=[key_name])
				# Key exists, append version
				import re
				match = re.search(r'-v(\d+)$', key_name)
				if match:
					version = int(match.group(1)) + 1
					key_name = re.sub(r'-v\d+$', f'-v{version}', key_name)
				else:
					key_name = f"{key_name}-v2"
			except ec2_client.exceptions.ClientError:
				# Key doesn't exist, proceed with creation
				pass
			
			key_response = ec2_client.create_key_pair(KeyName=key_name)
			key_material = key_response.get("KeyMaterial")
			
			# Store the key material as a password field
			self.db_set("ssh_key_name", key_name)
			self.set("ssh_private_key", key_material)
			self.save()
			
			frappe.msgprint(f"SSH key pair '{key_name}' created successfully. Private key stored securely.")
			
			return {
				"key_name": key_name,
				"key_material": key_material
			}
			
		except Exception as e:
			frappe.throw(f"Failed to create SSH key pair: {str(e)}")

	def get_ssh_private_key(self):
		"""Get the SSH private key for this cloud provider"""
		return get_decrypted_password("Cloud Provider", self.name, "ssh_private_key")
	
	@frappe.whitelist()
	def update_instance_ssh_key(self, instance_id, new_ssh_key_name):
		"""Update an instance to use a new SSH key by recreating it"""
		if self.provider_type != "AWS EC2":
			frappe.throw("SSH key update is only supported for AWS EC2")
		
		try:
			ec2_client = self.get_aws_client()
			
			# Get instance details
			response = ec2_client.describe_instances(InstanceIds=[instance_id])
			instance = response["Reservations"][0]["Instances"][0]
			
			# Terminate the old instance
			ec2_client.terminate_instances(InstanceIds=[instance_id])
			
			# Wait for instance to terminate
			ec2_client.get_waiter('instance_terminated').wait(InstanceIds=[instance_id])
			
			# Create new instance with new SSH key
			# This is a simplified version - in production you'd want to preserve all settings
			frappe.msgprint(f"Instance {instance_id} terminated. Please create a new instance with SSH key {new_ssh_key_name}")
			
			return {"status": "Instance terminated, please create new instance"}
			
		except Exception as e:
			frappe.throw(f"Failed to update instance SSH key: {str(e)}")


@frappe.whitelist()
def configure_instance_ssh(cloud_provider_name, instance_id):
	"""Test SSH connection with stored key and provide instructions"""
	cloud_provider = frappe.get_doc('Cloud Provider', cloud_provider_name)
	
	if cloud_provider.provider_type != "AWS EC2":
		frappe.throw("SSH configuration is only supported for AWS EC2")
	
	try:
		ec2_client = cloud_provider.get_aws_client()
		
		# Get the private key from Cloud Provider
		private_key = cloud_provider.get_ssh_private_key()
		if not private_key:
			frappe.throw("SSH private key not found in Cloud Provider. Please create a new SSH key pair.")
		
		# Get instance details
		instance_response = ec2_client.describe_instances(InstanceIds=[instance_id])
		instance = instance_response["Reservations"][0]["Instances"][0]
		public_ip = instance.get('PublicIpAddress')
		
		if not public_ip:
			frappe.throw("Instance does not have a public IP. Cannot configure SSH.")
		
		# Test SSH connection
		import subprocess
		import tempfile
		import os
		
		# Create temporary key file
		with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as key_file:
			key_file.write(private_key)
			key_file_path = key_file.name
		
		os.chmod(key_file_path, 0o600)
		
		try:
			# Test SSH connection
			ssh_test_cmd = [
				"ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
				"-i", key_file_path, f"ubuntu@{public_ip}", "echo 'SSH connection successful'"
			]
			
			result = subprocess.run(ssh_test_cmd, capture_output=True, text=True, timeout=15)
			
			if result.returncode == 0:
				frappe.msgprint(f"SSH connection successful to {public_ip}. You can now deploy the agent.")
				return {"status": "SSH connection successful", "public_ip": public_ip}
			else:
				frappe.throw(f"SSH connection failed: {result.stderr}. Please connect via AWS Console and run: sudo ufw allow ssh && sudo systemctl restart ssh")
		except subprocess.TimeoutExpired:
			frappe.throw("SSH connection timed out. Please check security group and firewall settings.")
		finally:
			# Clean up temporary key file
			if os.path.exists(key_file_path):
				os.remove(key_file_path)
		
	except Exception as e:
		frappe.throw(f"Failed to test SSH connection: {str(e)}")


@frappe.whitelist()
def get_ami_for_region(cloud_provider_name):
	"""Get appropriate AMI ID for the current region using AWS SSM Parameter Store"""
	cloud_provider = frappe.get_doc("Cloud Provider", cloud_provider_name)
	
	try:
		import boto3
		ssm_client = boto3.client(
			'ssm',
			aws_access_key_id=cloud_provider.aws_access_key_id,
			aws_secret_access_key=cloud_provider.get_password('aws_secret_access_key'),
			region_name=cloud_provider.region
		)
		
		# Use the same parameter path as Press for latest Ubuntu 20.04
		architecture = "amd64"  # Default to amd64 for x86_64
		parameter_name = f"/aws/service/canonical/ubuntu/server/20.04/stable/current/{architecture}/hvm/ebs-gp2/ami-id"
		
		response = ssm_client.get_parameter(Name=parameter_name)
		return response["Parameter"]["Value"]
		
	except Exception as e:
		# Fallback to hardcoded AMI mapping if SSM fails
		frappe.log_error(f"Failed to get latest Ubuntu AMI from SSM: {str(e)}. Using fallback AMI.")
		ami_mapping = {
			"us-east-1": "ami-0c55b159cbfafe1f0",
			"us-east-2": "ami-0c55b159cbfafe1f0",
			"us-west-1": "ami-0c55b159cbfafe1f0",
			"us-west-2": "ami-0c55b159cbfafe1f0",
			"eu-west-1": "ami-0c55b159cbfafe1f0",
			"eu-west-2": "ami-0c55b159cbfafe1f0",
			"eu-central-1": "ami-0c55b159cbfafe1f0",
			"ap-south-1": "ami-0a1b0c508e1fa9fce",
			"ap-southeast-1": "ami-08b138b7cf65145b1",  # Ubuntu 20.04 LTS (Focal Fossa)
			"ap-southeast-2": "ami-005c9e06a21d032e4",
			"ap-northeast-1": "ami-005c9e06a21d032e4",
			"ap-northeast-2": "ami-005c9e06a21d032e4",
			"sa-east-1": "ami-005c9e06a21d032e4"
		}
		return ami_mapping.get(cloud_provider.region, "ami-0c55b159cbfafe1f0")


@frappe.whitelist()
def check_instance_status(instance_id):
	"""Check instance status, security groups, and network details"""
	cloud_provider = frappe.get_doc("Cloud Provider", "g92re56hf1")
	ec2_client = cloud_provider.get_aws_client()
	
	try:
		response = ec2_client.describe_instances(InstanceIds=[instance_id])
		instance = response["Reservations"][0]["Instances"][0]
		
		result = {
			"instance_id": instance["InstanceId"],
			"state": instance["State"]["Name"],
			"public_ip": instance.get("PublicIpAddress"),
			"private_ip": instance.get("PrivateIpAddress"),
			"instance_type": instance["InstanceType"],
			"ami_id": instance["ImageId"],
			"key_name": instance.get("KeyName"),
			"security_groups": [sg["GroupId"] for sg in instance.get("SecurityGroups", [])],
			"subnet_id": instance.get("SubnetId"),
			"vpc_id": instance.get("VpcId"),
			"status_checks": instance.get("Status", {})
		}
		
		# Get security group rules
		security_group_ids = result["security_groups"]
		if security_group_ids:
			sg_response = ec2_client.describe_security_groups(GroupIds=security_group_ids)
			result["security_group_rules"] = []
			for sg in sg_response["SecurityGroups"]:
				for rule in sg.get("IpPermissions", []):
					protocol = rule["IpProtocol"]
					from_port = rule.get("FromPort", "N/A")
					to_port = rule.get("ToPort", "N/A")
					for ip_range in rule.get("IpRanges", []):
						result["security_group_rules"].append({
							"protocol": protocol,
							"from_port": from_port,
							"to_port": to_port,
							"cidr": ip_range["CidrIp"]
						})
		
		return result
		
	except Exception as e:
		frappe.throw(f"Failed to check instance status: {str(e)}")


@frappe.whitelist()
def list_instances():
	"""List all EC2 instances"""
	cloud_provider = frappe.get_doc("Cloud Provider", "g92re56hf1")
	ec2_client = cloud_provider.get_aws_client()
	
	try:
		response = ec2_client.describe_instances()
		instances = []
		for reservation in response["Reservations"]:
			for instance in reservation["Instances"]:
				instances.append({
					"instance_id": instance["InstanceId"],
					"state": instance["State"]["Name"],
					"public_ip": instance.get("PublicIpAddress"),
					"private_ip": instance.get("PrivateIpAddress"),
					"instance_type": instance["InstanceType"],
					"ami_id": instance["ImageId"],
					"key_name": instance.get("KeyName"),
					"launch_time": instance.get("LaunchTime")
				})
		return instances
	except Exception as e:
		frappe.throw(f"Failed to list instances: {str(e)}")


@frappe.whitelist()
def get_ssh_private_key_for_test(cloud_provider_name):
	"""Get SSH private key for testing"""
	cloud_provider = frappe.get_doc("Cloud Provider", cloud_provider_name)
	return cloud_provider.get_ssh_private_key()


@frappe.whitelist()
def check_network_configuration(subnet_id):
	"""Check subnet and network ACL configuration"""
	cloud_provider = frappe.get_doc("Cloud Provider", "g92re56hf1")
	ec2_client = cloud_provider.get_aws_client()
	
	try:
		result = {}
		
		# Get subnet details
		subnet_response = ec2_client.describe_subnets(SubnetIds=[subnet_id])
		subnet = subnet_response["Subnets"][0]
		result["subnet"] = {
			"subnet_id": subnet["SubnetId"],
			"vpc_id": subnet["VpcId"],
			"cidr": subnet["CidrBlock"],
			"map_public_ip_on_launch": subnet["MapPublicIpOnLaunch"],
			"availability_zone": subnet["AvailabilityZone"]
		}
		
		# Get network ACL
		acl_response = ec2_client.describe_network_acls(Filters=[{"Name": "association.subnet-id", "Values": [subnet_id]}])
		if acl_response["NetworkAcls"]:
			acl = acl_response["NetworkAcls"][0]
			result["network_acl"] = {
				"acl_id": acl["NetworkAclId"],
				"is_default": acl["IsDefault"],
				"entries": acl["Entries"]
			}
		else:
			result["network_acl"] = {"error": "No ACL found for subnet"}
		
		# Get route tables for VPC
		route_response = ec2_client.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [subnet["VpcId"]]}])
		result["route_tables"] = []
		for rt in route_response["RouteTables"]:
			result["route_tables"].append({
				"route_table_id": rt["RouteTableId"],
				"routes": rt["Routes"],
				"associations": rt.get("Associations", [])
			})
		
		return result
		
	except Exception as e:
		frappe.throw(f"Failed to check network configuration: {str(e)}")


@frappe.whitelist()
def check_internet_gateway(vpc_id):
	"""Check Internet Gateway for VPC"""
	cloud_provider = frappe.get_doc("Cloud Provider", "g92re56hf1")
	ec2_client = cloud_provider.get_aws_client()
	
	try:
		response = ec2_client.describe_internet_gateways(Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}])
		return response["InternetGateways"]
	except Exception as e:
		frappe.throw(f"Failed to check Internet Gateway: {str(e)}")


@frappe.whitelist()
def fix_route_table(vpc_id, subnet_id):
	"""Fix route table by adding Internet Gateway route"""
	cloud_provider = frappe.get_doc("Cloud Provider", "g92re56hf1")
	ec2_client = cloud_provider.get_aws_client()
	
	try:
		# Get Internet Gateway
		igw_response = ec2_client.describe_internet_gateways(Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}])
		if not igw_response["InternetGateways"]:
			frappe.throw("No Internet Gateway found for VPC")
		
		igw_id = igw_response["InternetGateways"][0]["InternetGatewayId"]
		
		# Get route tables for VPC
		rt_response = ec2_client.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
		
		for rt in rt_response["RouteTables"]:
			# Check if this route table is associated with the subnet
			is_associated = False
			for assoc in rt.get("Associations", []):
				if assoc.get("SubnetId") == subnet_id or assoc.get("Main"):
					is_associated = True
					break
			
			if is_associated:
				# Check if route to Internet Gateway exists
				has_igw_route = False
				for route in rt["Routes"]:
					if route.get("DestinationCidrBlock") == "0.0.0.0/0" and route.get("GatewayId"):
						has_igw_route = True
						break
				
				if not has_igw_route:
					# Add route to Internet Gateway
					ec2_client.create_route(
						RouteTableId=rt["RouteTableId"],
						DestinationCidrBlock="0.0.0.0/0",
						GatewayId=igw_id
					)
					return {"status": "success", "message": f"Added Internet Gateway route to route table {rt['RouteTableId']}"}
		
		return {"status": "success", "message": "Route table already has Internet Gateway route"}
		
	except Exception as e:
		frappe.throw(f"Failed to fix route table: {str(e)}")
