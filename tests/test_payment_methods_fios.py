"""
Test module for Payment Methods and Fios (Credits/Payments) endpoints
Tests:
- POST/GET/PUT/DELETE /api/payment-methods - CRUD for payment methods
- GET /api/payment-methods/active - Only active payment methods
- POST /api/invoices - Invoice creation with payment_status (pagado/por_cobrar)
- GET /api/fios - List accounts receivable summary
- GET /api/fios/{client_document} - Get client detail with pending invoices
- POST /api/fios/{invoice_number}/payment - Register partial payment (abono)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def auth_headers():
    """Get authentication headers for all tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@boltrex.com",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


class TestPaymentMethodsCRUD:
    """Payment Methods CRUD endpoint tests"""
    
    def test_get_all_payment_methods(self, auth_headers):
        """Test GET /api/payment-methods - List all payment methods"""
        response = requests.get(f"{BASE_URL}/api/payment-methods", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # Should have default payment methods
        assert len(data) >= 1
        
        # Verify structure
        if data:
            pm = data[0]
            assert "name" in pm
            assert "is_active" in pm
            assert "created_at" in pm
    
    def test_get_active_payment_methods(self, auth_headers):
        """Test GET /api/payment-methods/active - Only active payment methods"""
        response = requests.get(f"{BASE_URL}/api/payment-methods/active", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        
        # All returned methods should be active
        for pm in data:
            assert pm["is_active"] == True, f"Payment method {pm['name']} should be active"
    
    def test_create_payment_method(self, auth_headers):
        """Test POST /api/payment-methods - Create new payment method"""
        unique_name = f"TEST_PayMethod_{uuid.uuid4().hex[:6]}"
        payload = {
            "name": unique_name,
            "description": "Test payment method for automated testing",
            "is_active": True
        }
        
        response = requests.post(f"{BASE_URL}/api/payment-methods", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == unique_name
        assert data["description"] == payload["description"]
        assert data["is_active"] == True
        
        # Verify by GET
        get_response = requests.get(f"{BASE_URL}/api/payment-methods", headers=auth_headers)
        assert get_response.status_code == 200
        all_methods = get_response.json()
        found = any(pm["name"] == unique_name for pm in all_methods)
        assert found, f"Created payment method {unique_name} not found in list"
        
        # Cleanup - delete the test payment method
        delete_response = requests.delete(f"{BASE_URL}/api/payment-methods/{unique_name}", headers=auth_headers)
        assert delete_response.status_code == 200
    
    def test_create_duplicate_payment_method_fails(self, auth_headers):
        """Test POST /api/payment-methods - Duplicate name should fail"""
        # First, get existing payment methods
        get_response = requests.get(f"{BASE_URL}/api/payment-methods", headers=auth_headers)
        assert get_response.status_code == 200
        existing = get_response.json()
        
        if existing:
            existing_name = existing[0]["name"]
            payload = {
                "name": existing_name,
                "description": "Duplicate test",
                "is_active": True
            }
            
            response = requests.post(f"{BASE_URL}/api/payment-methods", json=payload, headers=auth_headers)
            assert response.status_code == 400
            assert "ya existe" in response.json()["detail"].lower() or "already" in response.json()["detail"].lower()
    
    def test_update_payment_method(self, auth_headers):
        """Test PUT /api/payment-methods/{name} - Update payment method"""
        # Create a test payment method first
        unique_name = f"TEST_Update_{uuid.uuid4().hex[:6]}"
        create_payload = {
            "name": unique_name,
            "description": "Original description",
            "is_active": True
        }
        
        create_response = requests.post(f"{BASE_URL}/api/payment-methods", json=create_payload, headers=auth_headers)
        assert create_response.status_code == 200
        
        # Update it
        update_payload = {
            "description": "Updated description",
            "is_active": False
        }
        
        update_response = requests.put(f"{BASE_URL}/api/payment-methods/{unique_name}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200
        updated_data = update_response.json()
        
        assert updated_data["description"] == "Updated description"
        assert updated_data["is_active"] == False
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/payment-methods/{unique_name}", headers=auth_headers)
    
    def test_update_nonexistent_payment_method(self, auth_headers):
        """Test PUT /api/payment-methods/{name} - Non-existent method"""
        update_payload = {"description": "Test"}
        response = requests.put(f"{BASE_URL}/api/payment-methods/NONEXISTENT_METHOD_12345", json=update_payload, headers=auth_headers)
        assert response.status_code == 404
    
    def test_delete_payment_method(self, auth_headers):
        """Test DELETE /api/payment-methods/{name} - Delete payment method"""
        # Create a test payment method first
        unique_name = f"TEST_Delete_{uuid.uuid4().hex[:6]}"
        create_payload = {
            "name": unique_name,
            "description": "To be deleted",
            "is_active": True
        }
        
        create_response = requests.post(f"{BASE_URL}/api/payment-methods", json=create_payload, headers=auth_headers)
        assert create_response.status_code == 200
        
        # Delete it
        delete_response = requests.delete(f"{BASE_URL}/api/payment-methods/{unique_name}", headers=auth_headers)
        assert delete_response.status_code == 200
        
        # Verify it's gone
        get_response = requests.get(f"{BASE_URL}/api/payment-methods", headers=auth_headers)
        all_methods = get_response.json()
        found = any(pm["name"] == unique_name for pm in all_methods)
        assert not found, f"Deleted payment method {unique_name} still exists"
    
    def test_delete_nonexistent_payment_method(self, auth_headers):
        """Test DELETE /api/payment-methods/{name} - Non-existent method"""
        response = requests.delete(f"{BASE_URL}/api/payment-methods/NONEXISTENT_METHOD_12345", headers=auth_headers)
        assert response.status_code == 404


class TestInvoicePaymentStatus:
    """Test invoice creation with payment_status field"""
    
    def test_create_invoice_pagado_requires_payment_method(self, auth_headers):
        """Test POST /api/invoices - 'pagado' status requires payment_method"""
        # Get a client first
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert clients_response.status_code == 200
        clients = clients_response.json()
        
        if not clients:
            pytest.skip("No clients available for testing")
        
        client = clients[0]
        
        # Try to create invoice with 'pagado' but no payment_method
        invoice_payload = {
            "client_document": client["document_number"],
            "items": [{
                "barcode": "TEST001",
                "product_name": "Test Product",
                "quantity": 1,
                "unit_price": 100,
                "tax_rate": 19,
                "subtotal": 100,
                "tax_amount": 19,
                "total": 119
            }],
            "payment_status": "pagado",
            "payment_method": None  # Missing payment method
        }
        
        response = requests.post(f"{BASE_URL}/api/invoices", json=invoice_payload, headers=auth_headers)
        assert response.status_code == 400
        assert "forma de pago" in response.json()["detail"].lower() or "payment" in response.json()["detail"].lower()
    
    def test_create_invoice_por_cobrar_no_payment_method_required(self, auth_headers):
        """Test POST /api/invoices - 'por_cobrar' status doesn't require payment_method"""
        # Get a client and product first
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        products_response = requests.get(f"{BASE_URL}/api/products", headers=auth_headers)
        
        assert clients_response.status_code == 200
        assert products_response.status_code == 200
        
        clients = clients_response.json()
        products = products_response.json()
        
        if not clients or not products:
            pytest.skip("No clients or products available for testing")
        
        client = clients[0]
        product = [p for p in products if p.get("stock", 0) > 0]
        
        if not product:
            pytest.skip("No products with stock available")
        
        product = product[0]
        
        # Create invoice with 'por_cobrar' and no payment_method
        invoice_payload = {
            "client_document": client["document_number"],
            "items": [{
                "barcode": product["barcode"],
                "product_name": product["name"],
                "quantity": 1,
                "unit_price": 100,
                "tax_rate": product.get("tax_rate", 19),
                "subtotal": 100,
                "tax_amount": 19,
                "total": 119
            }],
            "payment_status": "por_cobrar",
            "payment_method": None
        }
        
        response = requests.post(f"{BASE_URL}/api/invoices", json=invoice_payload, headers=auth_headers)
        
        # Should succeed
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["payment_status"] == "por_cobrar"
        assert data["payment_method"] is None
        assert data["balance"] == data["total"]  # Full amount is pending
        assert data["amount_paid"] == 0
    
    def test_create_invoice_pagado_with_valid_payment_method(self, auth_headers):
        """Test POST /api/invoices - 'pagado' with valid payment_method"""
        # Get active payment methods
        pm_response = requests.get(f"{BASE_URL}/api/payment-methods/active", headers=auth_headers)
        assert pm_response.status_code == 200
        payment_methods = pm_response.json()
        
        if not payment_methods:
            pytest.skip("No active payment methods available")
        
        # Get a client and product
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        products_response = requests.get(f"{BASE_URL}/api/products", headers=auth_headers)
        
        clients = clients_response.json()
        products = [p for p in products_response.json() if p.get("stock", 0) > 0]
        
        if not clients or not products:
            pytest.skip("No clients or products with stock available")
        
        client = clients[0]
        product = products[0]
        payment_method = payment_methods[0]["name"]
        
        invoice_payload = {
            "client_document": client["document_number"],
            "items": [{
                "barcode": product["barcode"],
                "product_name": product["name"],
                "quantity": 1,
                "unit_price": 100,
                "tax_rate": product.get("tax_rate", 19),
                "subtotal": 100,
                "tax_amount": 19,
                "total": 119
            }],
            "payment_status": "pagado",
            "payment_method": payment_method
        }
        
        response = requests.post(f"{BASE_URL}/api/invoices", json=invoice_payload, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["payment_status"] == "pagado"
        assert data["payment_method"] == payment_method
        assert data["balance"] == 0  # Fully paid
        assert data["amount_paid"] == data["total"]
    
    def test_create_invoice_with_inactive_payment_method_fails(self, auth_headers):
        """Test POST /api/invoices - Inactive payment method should fail"""
        # Create an inactive payment method
        unique_name = f"TEST_Inactive_{uuid.uuid4().hex[:6]}"
        create_payload = {
            "name": unique_name,
            "description": "Inactive method for testing",
            "is_active": False
        }
        
        create_response = requests.post(f"{BASE_URL}/api/payment-methods", json=create_payload, headers=auth_headers)
        assert create_response.status_code == 200
        
        # Get a client
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        clients = clients_response.json()
        
        if not clients:
            requests.delete(f"{BASE_URL}/api/payment-methods/{unique_name}", headers=auth_headers)
            pytest.skip("No clients available")
        
        client = clients[0]
        
        # Try to create invoice with inactive payment method
        invoice_payload = {
            "client_document": client["document_number"],
            "items": [{
                "barcode": "TEST001",
                "product_name": "Test Product",
                "quantity": 1,
                "unit_price": 100,
                "tax_rate": 19,
                "subtotal": 100,
                "tax_amount": 19,
                "total": 119
            }],
            "payment_status": "pagado",
            "payment_method": unique_name
        }
        
        response = requests.post(f"{BASE_URL}/api/invoices", json=invoice_payload, headers=auth_headers)
        assert response.status_code == 400
        assert "no existe o no está activa" in response.json()["detail"].lower() or "not active" in response.json()["detail"].lower()
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/payment-methods/{unique_name}", headers=auth_headers)


class TestFiosEndpoints:
    """Test Fios (Credits/Payments) endpoints"""
    
    def test_get_fios_accounts_summary(self, auth_headers):
        """Test GET /api/fios - List accounts receivable summary"""
        response = requests.get(f"{BASE_URL}/api/fios", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        
        # Verify structure if there are accounts
        if data:
            account = data[0]
            assert "client_document" in account
            assert "client_name" in account
            assert "total_credit" in account
            assert "total_paid" in account
            assert "balance" in account
            assert "invoices_count" in account
            
            # Balance should be positive (pending)
            assert account["balance"] > 0
    
    def test_get_fios_client_detail(self, auth_headers):
        """Test GET /api/fios/{client_document} - Get client detail"""
        # First get accounts to find a client with pending invoices
        accounts_response = requests.get(f"{BASE_URL}/api/fios", headers=auth_headers)
        assert accounts_response.status_code == 200
        accounts = accounts_response.json()
        
        if not accounts:
            pytest.skip("No accounts with pending invoices")
        
        client_document = accounts[0]["client_document"]
        
        response = requests.get(f"{BASE_URL}/api/fios/{client_document}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "client" in data
        assert "summary" in data
        assert "invoices" in data
        assert "payment_history" in data
        
        # Verify client info
        assert data["client"]["document_number"] == client_document
        assert "name" in data["client"]
        
        # Verify summary
        assert "total_credit" in data["summary"]
        assert "total_paid" in data["summary"]
        assert "balance" in data["summary"]
        assert "invoices_count" in data["summary"]
        
        # Verify invoices
        assert isinstance(data["invoices"], list)
        if data["invoices"]:
            invoice = data["invoices"][0]
            assert "invoice_number" in invoice
            assert "total" in invoice
            assert "balance" in invoice
    
    def test_get_fios_client_not_found(self, auth_headers):
        """Test GET /api/fios/{client_document} - Client not found"""
        response = requests.get(f"{BASE_URL}/api/fios/NONEXISTENT_CLIENT_12345", headers=auth_headers)
        assert response.status_code == 404


class TestFioPayments:
    """Test Fio payment (abono) registration"""
    
    def test_register_partial_payment(self, auth_headers):
        """Test POST /api/fios/{invoice_number}/payment - Register partial payment"""
        # Get accounts to find an invoice with pending balance
        accounts_response = requests.get(f"{BASE_URL}/api/fios", headers=auth_headers)
        assert accounts_response.status_code == 200
        accounts = accounts_response.json()
        
        if not accounts:
            pytest.skip("No accounts with pending invoices")
        
        # Get client detail to find an invoice
        client_document = accounts[0]["client_document"]
        detail_response = requests.get(f"{BASE_URL}/api/fios/{client_document}", headers=auth_headers)
        assert detail_response.status_code == 200
        detail = detail_response.json()
        
        if not detail["invoices"]:
            pytest.skip("No pending invoices for this client")
        
        invoice = detail["invoices"][0]
        invoice_number = invoice["invoice_number"]
        current_balance = invoice["balance"]
        
        # Get active payment methods
        pm_response = requests.get(f"{BASE_URL}/api/payment-methods/active", headers=auth_headers)
        payment_methods = pm_response.json()
        
        if not payment_methods:
            pytest.skip("No active payment methods")
        
        payment_method = payment_methods[0]["name"]
        
        # Register a partial payment (half of balance)
        payment_amount = min(1000, current_balance / 2)  # Pay half or 1000, whichever is smaller
        
        payment_payload = {
            "amount": payment_amount,
            "payment_method": payment_method,
            "notes": "Test partial payment"
        }
        
        response = requests.post(f"{BASE_URL}/api/fios/{invoice_number}/payment", json=payment_payload, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "payment" in data
        assert "invoice_update" in data
        
        # Verify payment details
        assert data["payment"]["amount"] == payment_amount
        assert data["payment"]["payment_method"] == payment_method
        
        # Verify invoice update
        assert data["invoice_update"]["new_balance"] == current_balance - payment_amount
    
    def test_payment_exceeds_balance_fails(self, auth_headers):
        """Test POST /api/fios/{invoice_number}/payment - Payment exceeds balance"""
        # Get accounts to find an invoice
        accounts_response = requests.get(f"{BASE_URL}/api/fios", headers=auth_headers)
        accounts = accounts_response.json()
        
        if not accounts:
            pytest.skip("No accounts with pending invoices")
        
        client_document = accounts[0]["client_document"]
        detail_response = requests.get(f"{BASE_URL}/api/fios/{client_document}", headers=auth_headers)
        detail = detail_response.json()
        
        if not detail["invoices"]:
            pytest.skip("No pending invoices")
        
        invoice = detail["invoices"][0]
        invoice_number = invoice["invoice_number"]
        current_balance = invoice["balance"]
        
        # Get active payment methods
        pm_response = requests.get(f"{BASE_URL}/api/payment-methods/active", headers=auth_headers)
        payment_methods = pm_response.json()
        
        if not payment_methods:
            pytest.skip("No active payment methods")
        
        # Try to pay more than balance
        payment_payload = {
            "amount": current_balance + 1000,  # Exceeds balance
            "payment_method": payment_methods[0]["name"],
            "notes": "Test exceeding payment"
        }
        
        response = requests.post(f"{BASE_URL}/api/fios/{invoice_number}/payment", json=payment_payload, headers=auth_headers)
        assert response.status_code == 400
        assert "excede" in response.json()["detail"].lower() or "exceed" in response.json()["detail"].lower()
    
    def test_payment_with_inactive_method_fails(self, auth_headers):
        """Test POST /api/fios/{invoice_number}/payment - Inactive payment method fails"""
        # Create an inactive payment method
        unique_name = f"TEST_InactiveFio_{uuid.uuid4().hex[:6]}"
        create_payload = {
            "name": unique_name,
            "description": "Inactive for fio test",
            "is_active": False
        }
        
        create_response = requests.post(f"{BASE_URL}/api/payment-methods", json=create_payload, headers=auth_headers)
        assert create_response.status_code == 200
        
        # Get an invoice
        accounts_response = requests.get(f"{BASE_URL}/api/fios", headers=auth_headers)
        accounts = accounts_response.json()
        
        if not accounts:
            requests.delete(f"{BASE_URL}/api/payment-methods/{unique_name}", headers=auth_headers)
            pytest.skip("No accounts with pending invoices")
        
        client_document = accounts[0]["client_document"]
        detail_response = requests.get(f"{BASE_URL}/api/fios/{client_document}", headers=auth_headers)
        detail = detail_response.json()
        
        if not detail["invoices"]:
            requests.delete(f"{BASE_URL}/api/payment-methods/{unique_name}", headers=auth_headers)
            pytest.skip("No pending invoices")
        
        invoice_number = detail["invoices"][0]["invoice_number"]
        
        # Try to pay with inactive method
        payment_payload = {
            "amount": 100,
            "payment_method": unique_name,
            "notes": "Test with inactive method"
        }
        
        response = requests.post(f"{BASE_URL}/api/fios/{invoice_number}/payment", json=payment_payload, headers=auth_headers)
        assert response.status_code == 400
        assert "no existe o no está activa" in response.json()["detail"].lower() or "not active" in response.json()["detail"].lower()
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/payment-methods/{unique_name}", headers=auth_headers)
    
    def test_payment_zero_amount_fails(self, auth_headers):
        """Test POST /api/fios/{invoice_number}/payment - Zero amount fails"""
        accounts_response = requests.get(f"{BASE_URL}/api/fios", headers=auth_headers)
        accounts = accounts_response.json()
        
        if not accounts:
            pytest.skip("No accounts with pending invoices")
        
        client_document = accounts[0]["client_document"]
        detail_response = requests.get(f"{BASE_URL}/api/fios/{client_document}", headers=auth_headers)
        detail = detail_response.json()
        
        if not detail["invoices"]:
            pytest.skip("No pending invoices")
        
        invoice_number = detail["invoices"][0]["invoice_number"]
        
        pm_response = requests.get(f"{BASE_URL}/api/payment-methods/active", headers=auth_headers)
        payment_methods = pm_response.json()
        
        if not payment_methods:
            pytest.skip("No active payment methods")
        
        payment_payload = {
            "amount": 0,
            "payment_method": payment_methods[0]["name"],
            "notes": "Test zero payment"
        }
        
        response = requests.post(f"{BASE_URL}/api/fios/{invoice_number}/payment", json=payment_payload, headers=auth_headers)
        assert response.status_code == 400
        assert "mayor a 0" in response.json()["detail"].lower() or "greater than" in response.json()["detail"].lower()
    
    def test_payment_on_nonexistent_invoice_fails(self, auth_headers):
        """Test POST /api/fios/{invoice_number}/payment - Non-existent invoice"""
        pm_response = requests.get(f"{BASE_URL}/api/payment-methods/active", headers=auth_headers)
        payment_methods = pm_response.json()
        
        if not payment_methods:
            pytest.skip("No active payment methods")
        
        payment_payload = {
            "amount": 100,
            "payment_method": payment_methods[0]["name"],
            "notes": "Test"
        }
        
        response = requests.post(f"{BASE_URL}/api/fios/INV-999999/payment", json=payment_payload, headers=auth_headers)
        assert response.status_code == 404


class TestUnauthorizedAccess:
    """Test unauthorized access to new endpoints"""
    
    def test_payment_methods_unauthorized(self):
        """Test GET /api/payment-methods without auth"""
        response = requests.get(f"{BASE_URL}/api/payment-methods")
        assert response.status_code in [401, 403]
    
    def test_payment_methods_active_unauthorized(self):
        """Test GET /api/payment-methods/active without auth"""
        response = requests.get(f"{BASE_URL}/api/payment-methods/active")
        assert response.status_code in [401, 403]
    
    def test_fios_unauthorized(self):
        """Test GET /api/fios without auth"""
        response = requests.get(f"{BASE_URL}/api/fios")
        assert response.status_code in [401, 403]
    
    def test_fios_client_unauthorized(self):
        """Test GET /api/fios/{client_document} without auth"""
        response = requests.get(f"{BASE_URL}/api/fios/123456")
        assert response.status_code in [401, 403]
    
    def test_fios_payment_unauthorized(self):
        """Test POST /api/fios/{invoice_number}/payment without auth"""
        response = requests.post(f"{BASE_URL}/api/fios/INV-000001/payment", json={"amount": 100, "payment_method": "Efectivo"})
        assert response.status_code in [401, 403]
