import click
import frappe

def execute():
    """Fix VM provisioning by adding AMI and correct Cloud Provider"""
    try:
        # List all Cloud Providers
        providers = frappe.get_all("Cloud Provider", fields=["name", "provider_type", "region"])
        print("Available Cloud Providers:")
        for p in providers:
            print(f"  Name: {p['name']}, Type: {p['provider_type']}, Region: {p['region']}")
        
        # Get the first available Cloud Provider
        if providers:
            provider_name = providers[0]['name']
            print(f"\nUsing Cloud Provider: {provider_name}")
            
            # Add ami_id column if needed
            try:
                frappe.db.sql("ALTER TABLE `tabVirtual Machine` ADD COLUMN `ami_id` VARCHAR(255)")
                print("Added ami_id column")
            except:
                print("ami_id column might already exist")
            
            # Update the VM
            vm = frappe.get_doc("Virtual Machine", "kd68me3o2u")
            vm.ami_id = "ami-0a1b0c508e1fa9fce"
            vm.cloud_provider = provider_name
            vm.save()
            print(f"VM updated with AMI: {vm.ami_id} and Cloud Provider: {provider_name}")
            
            # Provision the instance
            result = vm.provision_instance()
            print(f"Instance provisioned: {result}")
            
            # Check status
            vm.reload()
            print(f"Status: {vm.status}")
            print(f"Instance ID: {vm.instance_id}")
            print(f"Public IP: {vm.public_ip}")
        else:
            print("No Cloud Providers found!")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
