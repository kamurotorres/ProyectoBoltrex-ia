import requests
import sys
import json
from datetime import datetime, timedelta

class BoltrexAPITester:
    def __init__(self, base_url="https://boltrex-inventory.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_user_email = f"test_user_{datetime.now().strftime('%H%M%S')}@test.com"
        self.test_category = f"TestCategory_{datetime.now().strftime('%H%M%S')}"
        self.test_product_barcode = f"TEST{datetime.now().strftime('%H%M%S')}"
        self.test_client_doc = f"TEST{datetime.now().strftime('%H%M%S')}"

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json() if response.content else {}
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"   Response: {response.json()}")
                except:
                    print(f"   Response: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_auth_flow(self):
        """Test complete authentication flow"""
        print("\n" + "="*50)
        print("TESTING AUTHENTICATION")
        print("="*50)
        
        # Test registration
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data={
                "email": self.test_user_email,
                "password": "TestPass123!",
                "full_name": "Test User",
                "role": "admin"
            }
        )
        if not success:
            return False

        # Test login
        success, response = self.run_test(
            "User Login",
            "POST",
            "auth/login",
            200,
            data={
                "email": self.test_user_email,
                "password": "TestPass123!"
            }
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            print(f"   Token obtained: {self.token[:20]}...")
        else:
            return False

        # Test get current user
        success, _ = self.run_test(
            "Get Current User",
            "GET",
            "auth/me",
            200
        )
        return success

    def test_categories(self):
        """Test categories CRUD operations"""
        print("\n" + "="*50)
        print("TESTING CATEGORIES")
        print("="*50)

        # Create category
        success, response = self.run_test(
            "Create Category",
            "POST",
            "categories",
            200,
            data={
                "name": self.test_category,
                "description": "Test category description"
            }
        )
        if not success:
            return False

        # Get categories
        success, response = self.run_test(
            "Get Categories",
            "GET",
            "categories",
            200
        )
        if not success:
            return False

        # Update category
        success, _ = self.run_test(
            "Update Category",
            "PUT",
            f"categories/{self.test_category}",
            200,
            data={
                "name": self.test_category,
                "description": "Updated description"
            }
        )
        if not success:
            return False

        return True

    def test_products(self):
        """Test products CRUD operations"""
        print("\n" + "="*50)
        print("TESTING PRODUCTS")
        print("="*50)

        # Create product
        success, response = self.run_test(
            "Create Product",
            "POST",
            "products",
            200,
            data={
                "barcode": self.test_product_barcode,
                "name": "Test Product",
                "description": "Test product description",
                "category": self.test_category,
                "purchase_price": 10.50,
                "tax_rate": 19.0,
                "prices": [
                    {"price_list_name": "default", "price": 15.75}
                ]
            }
        )
        if not success:
            return False

        # Get products
        success, response = self.run_test(
            "Get Products",
            "GET",
            "products",
            200
        )
        if not success:
            return False

        # Search products
        success, response = self.run_test(
            "Search Products",
            "GET",
            "products",
            200,
            params={"search": "Test"}
        )
        if not success:
            return False

        # Get specific product
        success, _ = self.run_test(
            "Get Product by Barcode",
            "GET",
            f"products/{self.test_product_barcode}",
            200
        )
        if not success:
            return False

        return True

    def test_clients(self):
        """Test clients CRUD operations"""
        print("\n" + "="*50)
        print("TESTING CLIENTS")
        print("="*50)

        # Get document types first
        success, doc_types = self.run_test(
            "Get Document Types",
            "GET",
            "document-types",
            200
        )
        if not success or not doc_types:
            print("   No document types found, creating one...")
            success, _ = self.run_test(
                "Create Document Type",
                "POST",
                "document-types",
                200,
                data={"code": "CC", "name": "Cédula de Ciudadanía"}
            )
            if not success:
                return False

        # Create client
        success, response = self.run_test(
            "Create Client",
            "POST",
            "clients",
            200,
            data={
                "document_type": "CC",
                "document_number": self.test_client_doc,
                "first_name": "Test",
                "last_name": "Client",
                "phone": "1234567890",
                "email": "testclient@test.com",
                "address": "Test Address",
                "price_list": "default"
            }
        )
        if not success:
            return False

        # Get clients
        success, response = self.run_test(
            "Get Clients",
            "GET",
            "clients",
            200
        )
        if not success:
            return False

        # Search clients
        success, response = self.run_test(
            "Search Clients",
            "GET",
            "clients",
            200,
            params={"search": "Test"}
        )
        if not success:
            return False

        return True

    def test_pos_workflow(self):
        """Test complete POS workflow"""
        print("\n" + "="*50)
        print("TESTING POS WORKFLOW")
        print("="*50)

        # First, add some stock to the product (simulate purchase)
        success, _ = self.run_test(
            "Create Purchase (Add Stock)",
            "POST",
            "purchases",
            200,
            data={
                "supplier_name": "Test Supplier",
                "items": [
                    {
                        "barcode": self.test_product_barcode,
                        "product_name": "Test Product",
                        "quantity": 50,
                        "unit_cost": 10.50,
                        "total": 525.0
                    }
                ]
            }
        )
        if not success:
            return False

        # Create invoice (POS sale)
        success, response = self.run_test(
            "Create Invoice (POS Sale)",
            "POST",
            "invoices",
            200,
            data={
                "client_document": self.test_client_doc,
                "items": [
                    {
                        "barcode": self.test_product_barcode,
                        "product_name": "Test Product",
                        "quantity": 2,
                        "unit_price": 15.75,
                        "tax_rate": 19.0,
                        "subtotal": 31.50,
                        "tax_amount": 5.985,
                        "total": 37.485
                    }
                ]
            }
        )
        if not success:
            return False

        invoice_number = response.get('invoice_number')
        print(f"   Invoice created: {invoice_number}")

        # Get invoices
        success, _ = self.run_test(
            "Get Invoices",
            "GET",
            "invoices",
            200
        )
        if not success:
            return False

        # Get specific invoice
        if invoice_number:
            success, _ = self.run_test(
                "Get Invoice by Number",
                "GET",
                f"invoices/{invoice_number}",
                200
            )
            if not success:
                return False

        return True

    def test_inventory(self):
        """Test inventory operations"""
        print("\n" + "="*50)
        print("TESTING INVENTORY")
        print("="*50)

        # Get inventory
        success, response = self.run_test(
            "Get Inventory",
            "GET",
            "inventory",
            200
        )
        if not success:
            return False

        # Get inventory movements
        success, response = self.run_test(
            "Get Inventory Movements",
            "GET",
            "inventory/movements",
            200
        )
        if not success:
            return False

        # Get movements for specific product
        success, response = self.run_test(
            "Get Product Movements",
            "GET",
            "inventory/movements",
            200,
            params={"barcode": self.test_product_barcode}
        )
        if not success:
            return False

        return True

    def test_reports(self):
        """Test reports functionality"""
        print("\n" + "="*50)
        print("TESTING REPORTS")
        print("="*50)

        # Get sales report
        success, response = self.run_test(
            "Get Sales Report",
            "GET",
            "reports/sales",
            200
        )
        if not success:
            return False

        # Get sales report with date filter
        today = datetime.now().strftime('%Y-%m-%d')
        success, response = self.run_test(
            "Get Sales Report (Filtered)",
            "GET",
            "reports/sales",
            200,
            params={"start_date": today, "end_date": today}
        )
        if not success:
            return False

        # Get inventory report
        success, response = self.run_test(
            "Get Inventory Report",
            "GET",
            "reports/inventory",
            200
        )
        if not success:
            return False

        return True

    def test_dashboard(self):
        """Test dashboard statistics"""
        print("\n" + "="*50)
        print("TESTING DASHBOARD")
        print("="*50)

        success, response = self.run_test(
            "Get Dashboard Stats",
            "GET",
            "dashboard/stats",
            200
        )
        if success and response:
            print(f"   Total Products: {response.get('total_products', 0)}")
            print(f"   Total Clients: {response.get('total_clients', 0)}")
            print(f"   Total Invoices: {response.get('total_invoices', 0)}")
            print(f"   Total Sales: ${response.get('total_sales', 0):.2f}")
            print(f"   Low Stock Products: {response.get('low_stock_products', 0)}")

        return success

    def cleanup(self):
        """Clean up test data"""
        print("\n" + "="*50)
        print("CLEANING UP TEST DATA")
        print("="*50)

        # Delete test product
        self.run_test(
            "Delete Test Product",
            "DELETE",
            f"products/{self.test_product_barcode}",
            200
        )

        # Delete test category
        self.run_test(
            "Delete Test Category",
            "DELETE",
            f"categories/{self.test_category}",
            200
        )

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Boltrex API Testing...")
        print(f"Backend URL: {self.base_url}")
        
        test_results = {
            "auth": False,
            "categories": False,
            "products": False,
            "clients": False,
            "pos": False,
            "inventory": False,
            "reports": False,
            "dashboard": False
        }

        # Run tests in order
        if self.test_auth_flow():
            test_results["auth"] = True
            
            if self.test_categories():
                test_results["categories"] = True
                
                if self.test_products():
                    test_results["products"] = True
                    
                    if self.test_clients():
                        test_results["clients"] = True
                        
                        if self.test_pos_workflow():
                            test_results["pos"] = True
                            
                            if self.test_inventory():
                                test_results["inventory"] = True
                                
                                if self.test_reports():
                                    test_results["reports"] = True
                                    
                                    if self.test_dashboard():
                                        test_results["dashboard"] = True

        # Cleanup
        self.cleanup()

        # Print final results
        print("\n" + "="*60)
        print("FINAL TEST RESULTS")
        print("="*60)
        print(f"📊 Tests passed: {self.tests_passed}/{self.tests_run}")
        print(f"📈 Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        print("\n📋 Module Results:")
        for module, passed in test_results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {module.upper()}: {status}")

        return test_results, self.tests_passed, self.tests_run

def main():
    tester = BoltrexAPITester()
    test_results, passed, total = tester.run_all_tests()
    
    # Return appropriate exit code
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())