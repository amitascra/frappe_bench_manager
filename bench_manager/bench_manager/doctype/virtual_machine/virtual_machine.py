# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password
from datetime import datetime


class VirtualMachine(Document):
	def validate(self):
		if self.cloud_provider:
			cloud_provider = frappe.get_doc("Cloud Provider", self.cloud_provider)
			if cloud_provider.provider_type != "AWS EC2":
				frappe.throw("Only AWS EC2 is supported at this time")
			
			# Auto-inherit region from Cloud Provider
			if not self.region or self.region != cloud_provider.region:
				self.region = cloud_provider.region
			
			# Auto-set AMI from Cloud Provider's region mapping
			if not self.ami_id:
				from bench_manager.bench_manager.doctype.cloud_provider.cloud_provider import get_ami_for_region
				self.ami_id = get_ami_for_region(self.cloud_provider)
		
		self.set_instance_specs()

	def set_instance_specs(self):
		"""Set vCPU and RAM based on instance type"""
		instance_specs = {
			"t3.micro": {"vcpu": 2, "ram": 1},
			"t3.small": {"vcpu": 2, "ram": 2},
			"t3.medium": {"vcpu": 2, "ram": 4},
			"t3.large": {"vcpu": 2, "ram": 8},
			"t3.xlarge": {"vcpu": 4, "ram": 16},
			"t3.2xlarge": {"vcpu": 8, "ram": 32},
			"t4.micro": {"vcpu": 2, "ram": 1},
			"t4.small": {"vcpu": 2, "ram": 2},
			"t4.medium": {"vcpu": 2, "ram": 4},
			"t4.large": {"vcpu": 2, "ram": 8},
			"t4.xlarge": {"vcpu": 4, "ram": 16},
			"t4.2xlarge": {"vcpu": 8, "ram": 32},
			"m5.large": {"vcpu": 2, "ram": 8},
			"m5.xlarge": {"vcpu": 4, "ram": 16},
			"m5.2xlarge": {"vcpu": 8, "ram": 32},
			"m5.4xlarge": {"vcpu": 16, "ram": 64},
			"m5.8xlarge": {"vcpu": 32, "ram": 128},
			"m5.12xlarge": {"vcpu": 48, "ram": 192},
			"m5.16xlarge": {"vcpu": 64, "ram": 256},
			"m5.24xlarge": {"vcpu": 96, "ram": 384},
			"c5.large": {"vcpu": 2, "ram": 4},
			"c5.xlarge": {"vcpu": 4, "ram": 8},
			"c5.2xlarge": {"vcpu": 8, "ram": 16},
			"c5.4xlarge": {"vcpu": 16, "ram": 32},
			"c5.9xlarge": {"vcpu": 36, "ram": 72},
			"c5.18xlarge": {"vcpu": 72, "ram": 144},
			"r5.large": {"vcpu": 2, "ram": 16},
			"r5.xlarge": {"vcpu": 4, "ram": 32},
			"r5.2xlarge": {"vcpu": 8, "ram": 64},
			"r5.4xlarge": {"vcpu": 16, "ram": 128},
			"r5.8xlarge": {"vcpu": 32, "ram": 256},
			"r5.12xlarge": {"vcpu": 48, "ram": 384},
			"r5.16xlarge": {"vcpu": 64, "ram": 512},
			"r5.24xlarge": {"vcpu": 96, "ram": 768}
		}
		
		if self.instance_type in instance_specs:
			self.vcpu = instance_specs[self.instance_type]["vcpu"]
			self.ram = instance_specs[self.instance_type]["ram"]

	def get_cloud_provider(self):
		"""Get cloud provider document"""
		return frappe.get_doc("Cloud Provider", self.cloud_provider)

	@frappe.whitelist()
	def provision_instance(self):
		"""Provision EC2 instance"""
		try:
			cloud_provider = self.get_cloud_provider()
			ec2_client = cloud_provider.get_aws_client()
			
			# Ensure VPC and subnet are provisioned (auto-provision if missing)
			if not cloud_provider.vpc_id:
				frappe.msgprint("Provisioning VPC...")
				cloud_provider.provision_vpc()
				cloud_provider.reload()
			
			# Get subnet ID
			subnet_id = cloud_provider.subnet_id
			if not subnet_id:
				frappe.msgprint("Provisioning VPC resources...")
				vpc_result = cloud_provider.provision_vpc()
				subnet_id = vpc_result.get("subnet_id")
				cloud_provider.reload()
			
			# Get security group ID
			security_group_id = cloud_provider.security_group_id
			if not security_group_id:
				vpc_result = cloud_provider.provision_vpc()
				security_group_id = vpc_result.get("security_group_id")
				cloud_provider.reload()
			
			# Get SSH key name
			ssh_key_name = cloud_provider.ssh_key_name
			if not ssh_key_name:
				key_response = cloud_provider.create_ssh_key_pair()
				ssh_key_name = key_response["key_name"]
			
			# Ensure we have the latest AMI
			if not self.ami_id:
				from bench_manager.bench_manager.doctype.cloud_provider.cloud_provider import get_ami_for_region
				self.ami_id = get_ami_for_region(self.cloud_provider)
				self.save()
			
			# Create instance with public IP assignment and user data script
			# Use cloud-config format like Press to add SSH key to authorized_keys
			# Get the public key from the SSH key pair
			key_pair_response = ec2_client.describe_key_pairs(KeyNames=[ssh_key_name])
			# Note: AWS doesn't return KeyMaterial for existing keys, so we'll use the key name
			# The SSH key will be automatically added by AWS when the instance is created
			
			# Simple cloud-config to ensure SSH is running
			user_data_script = """#cloud-config
runcmd:
- systemctl restart ssh
- systemctl enable ssh
"""
			
			# Base64 encode the user data script for cloud-init
			import base64
			user_data_encoded = base64.b64encode(user_data_script.encode('utf-8')).decode('utf-8')
			
			response = ec2_client.run_instances(
				ImageId=self.ami_id,
				InstanceType=self.instance_type,
				KeyName=ssh_key_name,
				MinCount=1,
				MaxCount=1,
				UserData=user_data_encoded,
				NetworkInterfaces=[
					{
						"SubnetId": subnet_id,
						"DeviceIndex": 0,
						"AssociatePublicIpAddress": True,
						"Groups": [security_group_id]
					}
				],
				TagSpecifications=[
					{
						"ResourceType": "instance",
						"Tags": [
							{"Key": "Name", "Value": f"BenchManager-{self.name}"}
						]
					}
				]
			)
			
			instance_id = response["Instances"][0]["InstanceId"]
			
			# Wait for instance to be running
			ec2_client.get_waiter("instance_running").wait(InstanceIds=[instance_id])
			
			# Get instance details
			instance_response = ec2_client.describe_instances(InstanceIds=[instance_id])
			instance = instance_response["Reservations"][0]["Instances"][0]
			
			# Update Virtual Machine with instance details
			self.db_set({
				"instance_id": instance_id,
				"public_ip": instance.get("PublicIpAddress"),
				"private_ip": instance.get("PrivateIpAddress"),
				"ssh_key_name": ssh_key_name,
				"vpc_id": cloud_provider.vpc_id,
				"subnet_id": subnet_id,
				"security_group_id": security_group_id,
				"status": "Running",
				"created_at": datetime.now()
			})
			
			return {
				"instance_id": instance_id,
				"public_ip": instance.get("PublicIpAddress"),
				"private_ip": instance.get("PrivateIpAddress")
			}
			
		except Exception as e:
			self.db_set("status", "Failed")
			frappe.throw(f"Failed to provision instance: {str(e)}")

	@frappe.whitelist()
	def start_instance(self):
		"""Start EC2 instance"""
		try:
			cloud_provider = self.get_cloud_provider()
			ec2_client = cloud_provider.get_aws_client()
			
			ec2_client.start_instances(InstanceIds=[self.instance_id])
			ec2_client.get_waiter("instance_running").wait(InstanceIds=[self.instance_id])
			
			self.db_set("status", "Running")
			return {"status": "Running"}
			
		except Exception as e:
			frappe.throw(f"Failed to start instance: {str(e)}")

	@frappe.whitelist()
	def stop_instance(self):
		"""Stop EC2 instance"""
		try:
			cloud_provider = self.get_cloud_provider()
			ec2_client = cloud_provider.get_aws_client()
			
			ec2_client.stop_instances(InstanceIds=[self.instance_id])
			ec2_client.get_waiter("instance_stopped").wait(InstanceIds=[self.instance_id])
			
			self.db_set("status", "Stopped")
			return {"status": "Stopped"}
			
		except Exception as e:
			frappe.throw(f"Failed to stop instance: {str(e)}")

	@frappe.whitelist()
	def terminate_instance(self):
		"""Terminate EC2 instance"""
		try:
			cloud_provider = self.get_cloud_provider()
			ec2_client = cloud_provider.get_aws_client()
			
			ec2_client.terminate_instances(InstanceIds=[self.instance_id])
			ec2_client.get_waiter("instance_terminated").wait(InstanceIds=[self.instance_id])
			
			self.db_set("status", "Terminated")
			return {"status": "Terminated"}
			
		except Exception as e:
			frappe.throw(f"Failed to terminate instance: {str(e)}")

	@frappe.whitelist()
	def deploy_agent(self):
		"""Deploy agent to the virtual machine using Ansible playbooks"""
		import os
		import subprocess
		from frappe.utils.password import get_decrypted_password

		try:
			# Get SSH key from Cloud Provider
			cloud_provider = self.get_cloud_provider()
			
			# Get SSH key path from Cloud Provider
			ssh_key_path = None
			frappe.publish_realtime(
				f"agent_deployment_{self.name}",
				{"status": "running", "message": f"Checking SSH key: {cloud_provider.ssh_key_name}", "progress": 12}
			)
			
			if cloud_provider.ssh_key_name:
				try:
					# Try to get the stored SSH private key
					private_key = cloud_provider.get_ssh_private_key()
					frappe.publish_realtime(
						f"agent_deployment_{self.name}",
						{"status": "running", "message": f"SSH key retrieved: {bool(private_key)}", "progress": 14}
					)
					
					if private_key:
						ssh_key_path = f"/tmp/{cloud_provider.ssh_key_name}.pem"
						# Write the SSH key to a temporary file
						with open(ssh_key_path, 'w') as f:
							f.write(private_key)
						os.chmod(ssh_key_path, 0o600)
						frappe.publish_realtime(
							f"agent_deployment_{self.name}",
							{"status": "running", "message": f"SSH key written to: {ssh_key_path}", "progress": 16}
						)
					else:
						# SSH key exists but private key not stored, create new key pair
						frappe.publish_realtime(
							f"agent_deployment_{self.name}",
							{"status": "running", "message": "Creating new SSH key pair...", "progress": 15}
						)
						key_response = cloud_provider.create_ssh_key_pair()
						ssh_key_path = f"/tmp/{key_response['key_name']}.pem"
						with open(ssh_key_path, 'w') as f:
							f.write(key_response['key_material'])
						os.chmod(ssh_key_path, 0o600)
						frappe.publish_realtime(
							f"agent_deployment_{self.name}",
							{"status": "running", "message": f"Created new SSH key: {key_response['key_name']}", "progress": 18}
						)
				except Exception as e:
					# If SSH key retrieval fails, log the error and skip SSH key auth
					import traceback
					error_details = f"{str(e)}\n{traceback.format_exc()}"
					frappe.publish_realtime(
						f"agent_deployment_{self.name}",
						{"status": "running", "message": f"SSH key retrieval failed: {str(e)}", "progress": 15}
					)
					frappe.log_error(f"SSH key retrieval failed: {error_details}")
			else:
				frappe.publish_realtime(
					f"agent_deployment_{self.name}",
					{"status": "running", "message": "No SSH key name configured in Cloud Provider", "progress": 15}
				)
			
			# Use public IP if available, otherwise use private IP
			target_ip = self.public_ip if self.public_ip else self.private_ip
			
			if not target_ip:
				frappe.throw("Virtual Machine must have a public or private IP to deploy agent")
			
			# Check VM status
			frappe.publish_realtime(
				f"agent_deployment_{self.name}",
				{"status": "running", "message": "Checking VM status...", "progress": 5}
			)
			
			status_info = self.get_instance_status()
			if status_info.get("status") != "Running":
				frappe.throw(f"VM is not running. Current status: {status_info.get('status')}")
			
			# Generate agent password if not set
			if not self.agent_password:
				import secrets
				self.agent_password = secrets.token_urlsafe(32)
				self.save()
			
			# Emit progress via Socket.io
			frappe.publish_realtime(
				f"agent_deployment_{self.name}",
				{"status": "started", "message": "Starting agent deployment..."}
			)
			
			frappe.publish_realtime(
				f"agent_deployment_{self.name}",
				{"status": "running", "message": "Running Ansible playbook...", "progress": 20}
			)
			
			# Get playbook path
			playbook_path = os.path.join(
				frappe.get_app_path("bench_manager"),
				"playbooks",
				"deploy_agent.yml"
			)
			
			# Create inventory file
			inventory_content = f"[agent_servers]\n{target_ip} ansible_user=ubuntu ansible_ssh_common_args='-o StrictHostKeyChecking=no' ansible_ssh_pipelining=no"
			if ssh_key_path:
				inventory_content += f" ansible_ssh_private_key_file={ssh_key_path}"
			inventory_content += "\n"
			inventory_path = os.path.join(frappe.get_site_path(), "agent_inventory.ini")
			with open(inventory_path, 'w') as f:
				f.write(inventory_content)
			
			# Run Ansible playbook
			extra_vars = {
				"agent_repository_url": "https://github.com/amitascra/bench_agent.git",
				"agent_branch": "develop",
				"server": self.name,
				"workers": 2,
				"press_url": "http://bench.amitkumar.live",
				"agent_password": self.agent_password,
				"certificate_private_key": "",
				"certificate_full_chain": "",
				"certificate_intermediate_chain": "",
			}
			
			extra_vars_str = " ".join([f"{k}='{v}'" for k, v in extra_vars.items()])
			
			cmd = [
				"ansible-playbook",
				playbook_path,
				"-i", inventory_path,
				"--extra-vars", extra_vars_str,
				"-vv"
			]
			
			frappe.publish_realtime(
				f"agent_deployment_{self.name}",
				{"status": "running", "message": "Deploying agent via Ansible...", "progress": 50}
			)
			
			result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
			
			if result.returncode != 0:
				error_output = f"STDERR:\n{result.stderr}\n\nSTDOUT:\n{result.stdout}"
				frappe.publish_realtime(
					f"agent_deployment_{self.name}",
					{"status": "failed", "message": "Ansible playbook failed", "error": error_output}
				)
				frappe.throw(f"Ansible playbook failed: {error_output}")
			
			# Update agent status
			self.db_set("agent_installed", 1)
			
			frappe.publish_realtime(
				f"agent_deployment_{self.name}",
				{"status": "completed", "message": "Agent deployed successfully!", "progress": 100}
			)
			
			# Clean up inventory file
			os.remove(inventory_path)
			
			# Clean up SSH key file if it was created
			if ssh_key_path and os.path.exists(ssh_key_path):
				os.remove(ssh_key_path)
			
			return {"status": "Agent deployed successfully"}
			
		except Exception as e:
			frappe.publish_realtime(
				f"agent_deployment_{self.name}",
				{"status": "failed", "message": f"Failed to deploy agent: {str(e)}"}
			)
			frappe.throw(f"Failed to deploy agent: {str(e)}")

	@frappe.whitelist()
	def get_instance_status(self):
		"""Get current instance status from AWS"""
		try:
			cloud_provider = self.get_cloud_provider()
			ec2_client = cloud_provider.get_aws_client()
			
			response = ec2_client.describe_instances(InstanceIds=[self.instance_id])
			instance = response["Reservations"][0]["Instances"][0]
			
			state = instance["State"]["Name"]
			self.db_set("status", state.capitalize())
			
			return {
				"status": state.capitalize(),
				"public_ip": instance.get("PublicIpAddress"),
				"private_ip": instance.get("PrivateIpAddress")
			}
			
		except Exception as e:
			frappe.throw(f"Failed to get instance status: {str(e)}")

	@frappe.whitelist()
	def associate_public_ip(self):
		"""Allocate and associate an Elastic IP to the instance"""
		try:
			cloud_provider = self.get_cloud_provider()
			ec2_client = cloud_provider.get_aws_client()
			
			# Allocate Elastic IP
			allocation_response = ec2_client.allocate_address(Domain='vpc')
			allocation_id = allocation_response['AllocationId']
			public_ip = allocation_response['PublicIp']
			
			# Associate Elastic IP with instance
			association_response = ec2_client.associate_address(
				InstanceId=self.instance_id,
				AllocationId=allocation_id
			)
			
			# Update VM with public IP and allocation ID
			self.db_set({
				"public_ip": public_ip
			})
			
			return {
				"status": "success",
				"public_ip": public_ip,
				"allocation_id": allocation_id
			}
			
		except Exception as e:
			frappe.throw(f"Failed to associate public IP: {str(e)}")
