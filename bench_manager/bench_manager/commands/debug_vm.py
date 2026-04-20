import frappe

def execute():
    """Debug Virtual Machine save error"""
    try:
        # Get the VM and check its current state
        vm = frappe.get_doc("Virtual Machine", "kd68me3o2u")
        print("Current VM state:")
        print(f"  Cloud Provider: {vm.cloud_provider}")
        print(f"  Instance Type: {vm.instance_type}")
        print(f"  AMI ID: {vm.ami_id}")
        print(f"  Region: {vm.region}")
        print(f"  Series: {vm.series}")
        print(f"  Disk Size: {vm.disk_size}")
        
        # List all Cloud Providers
        providers = frappe.get_all("Cloud Provider", fields=["name", "region"])
        print("\nAvailable Cloud Providers:")
        for p in providers:
            print(f"  {p['name']} - {p['region']}")
        
        # Check if Cloud Provider exists
        if vm.cloud_provider:
            try:
                cp = frappe.get_doc("Cloud Provider", vm.cloud_provider)
                print(f"\nCloud Provider exists: {cp.name}, Region: {cp.region}")
            except Exception as e:
                print(f"\nCloud Provider '{vm.cloud_provider}' does not exist: {e}")
        
        # Try to save and catch the error
        print("\nAttempting to save...")
        try:
            vm.save()
            print("Save successful!")
        except Exception as e:
            print(f"Save error: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
