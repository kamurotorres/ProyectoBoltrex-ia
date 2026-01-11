"""
Test module for Invoice listing and PDF ticket generation endpoints
Tests:
- GET /api/pos/invoices - List invoices with pagination and filters
- GET /api/pos/invoices/{invoice_number} - Get single invoice details
- GET /api/pos/invoices/{invoice_number}/ticket - Generate and download PDF ticket
- GET /api/ticket-config - Get ticket configuration
- PUT /api/ticket-config - Update ticket configuration
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests to get token for subsequent tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@boltrex.com",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@boltrex.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "admin@boltrex.com"


class TestTicketConfig:
    """Ticket configuration endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@boltrex.com",
            "password": "admin123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_ticket_config(self, auth_headers):
        """Test GET /api/ticket-config - Get ticket configuration"""
        response = requests.get(f"{BASE_URL}/api/ticket-config", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "company_name" in data
        assert "ticket_width" in data
        assert "footer_message" in data
        
        # Verify ticket_width is valid (58 or 80)
        assert data["ticket_width"] in [58, 80]
    
    def test_update_ticket_config_58mm(self, auth_headers):
        """Test PUT /api/ticket-config - Update to 58mm width"""
        update_data = {
            "company_name": "TEST_Boltrex Store",
            "nit": "900.123.456-7",
            "phone": "+57 300 123 4567",
            "email": "test@boltrex.com",
            "address": "Calle 123 #45-67, Bogotá",
            "ticket_width": 58,
            "footer_message": "¡Gracias por su compra! TEST"
        }
        
        response = requests.put(f"{BASE_URL}/api/ticket-config", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify update was applied
        assert data["company_name"] == "TEST_Boltrex Store"
        assert data["ticket_width"] == 58
        assert data["nit"] == "900.123.456-7"
        
        # Verify by GET
        get_response = requests.get(f"{BASE_URL}/api/ticket-config", headers=auth_headers)
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["ticket_width"] == 58
        assert get_data["company_name"] == "TEST_Boltrex Store"
    
    def test_update_ticket_config_80mm(self, auth_headers):
        """Test PUT /api/ticket-config - Update to 80mm width"""
        update_data = {
            "company_name": "Boltrex Inventory",
            "ticket_width": 80,
            "footer_message": "¡Gracias por su compra!"
        }
        
        response = requests.put(f"{BASE_URL}/api/ticket-config", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["ticket_width"] == 80
        assert data["company_name"] == "Boltrex Inventory"


class TestPOSInvoices:
    """POS Invoice listing endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@boltrex.com",
            "password": "admin123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_invoices_list(self, auth_headers):
        """Test GET /api/pos/invoices - List invoices with pagination"""
        response = requests.get(f"{BASE_URL}/api/pos/invoices", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "invoices" in data
        assert "pagination" in data
        assert isinstance(data["invoices"], list)
        
        # Verify pagination structure
        pagination = data["pagination"]
        assert "page" in pagination
        assert "limit" in pagination
        assert "total" in pagination
        assert "pages" in pagination
    
    def test_get_invoices_with_pagination(self, auth_headers):
        """Test GET /api/pos/invoices with pagination params"""
        response = requests.get(f"{BASE_URL}/api/pos/invoices?page=1&limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["limit"] == 5
        assert len(data["invoices"]) <= 5
    
    def test_get_invoices_filter_by_status(self, auth_headers):
        """Test GET /api/pos/invoices with status filter"""
        response = requests.get(f"{BASE_URL}/api/pos/invoices?status=completed", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # All returned invoices should have status 'completed'
        for invoice in data["invoices"]:
            assert invoice["status"] == "completed"
    
    def test_get_invoices_filter_by_invoice_number(self, auth_headers):
        """Test GET /api/pos/invoices with invoice_number filter"""
        response = requests.get(f"{BASE_URL}/api/pos/invoices?invoice_number=INV-000001", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Should find the invoice
        if data["invoices"]:
            assert "INV-000001" in data["invoices"][0]["invoice_number"]
    
    def test_get_single_invoice_detail(self, auth_headers):
        """Test GET /api/pos/invoices/{invoice_number} - Get single invoice"""
        # First get list to find an existing invoice
        list_response = requests.get(f"{BASE_URL}/api/pos/invoices", headers=auth_headers)
        assert list_response.status_code == 200
        invoices = list_response.json()["invoices"]
        
        if invoices:
            invoice_number = invoices[0]["invoice_number"]
            
            # Get single invoice detail
            response = requests.get(f"{BASE_URL}/api/pos/invoices/{invoice_number}", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            
            # Verify invoice structure
            assert data["invoice_number"] == invoice_number
            assert "client_name" in data
            assert "client_document" in data
            assert "items" in data
            assert "subtotal" in data
            assert "total_tax" in data
            assert "total" in data
            assert "created_by" in data
            assert "created_at" in data
            assert "status" in data
        else:
            pytest.skip("No invoices found in database")
    
    def test_get_invoice_not_found(self, auth_headers):
        """Test GET /api/pos/invoices/{invoice_number} - Invoice not found"""
        response = requests.get(f"{BASE_URL}/api/pos/invoices/INV-999999", headers=auth_headers)
        assert response.status_code == 404


class TestPDFTicketGeneration:
    """PDF Ticket generation endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@boltrex.com",
            "password": "admin123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_download_ticket_pdf(self, auth_headers):
        """Test GET /api/pos/invoices/{invoice_number}/ticket - Download PDF ticket"""
        # First get list to find an existing invoice
        list_response = requests.get(f"{BASE_URL}/api/pos/invoices", headers=auth_headers)
        assert list_response.status_code == 200
        invoices = list_response.json()["invoices"]
        
        if invoices:
            invoice_number = invoices[0]["invoice_number"]
            
            # Download PDF ticket
            response = requests.get(
                f"{BASE_URL}/api/pos/invoices/{invoice_number}/ticket", 
                headers=auth_headers
            )
            assert response.status_code == 200
            
            # Verify it's a PDF
            assert response.headers.get("content-type") == "application/pdf"
            
            # Verify content-disposition header
            content_disposition = response.headers.get("content-disposition", "")
            assert "attachment" in content_disposition
            assert f"ticket_{invoice_number}.pdf" in content_disposition
            
            # Verify PDF content starts with PDF magic bytes
            assert response.content[:4] == b'%PDF'
        else:
            pytest.skip("No invoices found in database")
    
    def test_download_ticket_invoice_not_found(self, auth_headers):
        """Test GET /api/pos/invoices/{invoice_number}/ticket - Invoice not found"""
        response = requests.get(
            f"{BASE_URL}/api/pos/invoices/INV-999999/ticket", 
            headers=auth_headers
        )
        assert response.status_code == 404


class TestInvoiceFilters:
    """Test invoice filtering functionality"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@boltrex.com",
            "password": "admin123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_filter_by_date_range(self, auth_headers):
        """Test filtering invoices by date range"""
        response = requests.get(
            f"{BASE_URL}/api/pos/invoices?start_date=2024-01-01&end_date=2025-12-31", 
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "invoices" in data
    
    def test_filter_by_user_email(self, auth_headers):
        """Test filtering invoices by user email"""
        response = requests.get(
            f"{BASE_URL}/api/pos/invoices?user_email=admin", 
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "invoices" in data
    
    def test_filter_by_client_document(self, auth_headers):
        """Test filtering invoices by client document"""
        response = requests.get(
            f"{BASE_URL}/api/pos/invoices?client_document=123", 
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "invoices" in data
    
    def test_combined_filters(self, auth_headers):
        """Test combining multiple filters"""
        response = requests.get(
            f"{BASE_URL}/api/pos/invoices?status=completed&page=1&limit=10", 
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "invoices" in data
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["limit"] == 10


class TestUnauthorizedAccess:
    """Test unauthorized access to endpoints"""
    
    def test_get_invoices_unauthorized(self):
        """Test GET /api/pos/invoices without auth"""
        response = requests.get(f"{BASE_URL}/api/pos/invoices")
        assert response.status_code in [401, 403]
    
    def test_get_ticket_config_unauthorized(self):
        """Test GET /api/ticket-config without auth"""
        response = requests.get(f"{BASE_URL}/api/ticket-config")
        assert response.status_code in [401, 403]
    
    def test_update_ticket_config_unauthorized(self):
        """Test PUT /api/ticket-config without auth"""
        response = requests.put(f"{BASE_URL}/api/ticket-config", json={"company_name": "Test"})
        assert response.status_code in [401, 403]
    
    def test_download_ticket_unauthorized(self):
        """Test GET /api/pos/invoices/{invoice_number}/ticket without auth"""
        response = requests.get(f"{BASE_URL}/api/pos/invoices/INV-000001/ticket")
        assert response.status_code in [401, 403]
