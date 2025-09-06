// Quick Order JavaScript Functions
let currentStep = 1;
let selectedCustomer = null;
let selectedVehicle = null;
let vehicleCustomer = null; // Customer from selected vehicle
let selectedServices = [];
let selectedInventoryItems = [];
let selectedPackage = null;
let allServices = [];
let serviceType = 'individual'; // 'individual' or 'package'
let orderType = null; // 'search-vehicle', 'register-vehicle', 'items-only'

// Order Type Management
function selectOrderType(type, element) {
    console.log('selectOrderType called with type:', type, 'element:', element);
    
    orderType = type;
    
    // Update hidden field for form submission
    const orderTypeField = document.getElementById('orderType');
    if (orderTypeField) {
        orderTypeField.value = type;
        console.log('Set order type field to:', type);
    } else {
        console.error('orderType field not found');
    }
    
    // Update card selection visually
    document.querySelectorAll('.order-type-card').forEach(card => {
        card.classList.remove('selected');
    });
    if (element) {
        element.classList.add('selected');
        console.log('Added selected class to element');
    }
    
    // Hide all sections first
    const sections = {
        vehicleSearchSection: document.getElementById('vehicleSearchSection'),
        selectedVehicleDisplay: document.getElementById('selectedVehicleDisplay'),
        newVehicleForm: document.getElementById('newVehicleForm'),
        itemsOnlyCustomerSection: document.getElementById('itemsOnlyCustomerSection')
    };
    
    Object.values(sections).forEach(section => {
        if (section) section.style.display = 'none';
    });
    
    // Show relevant sections based on selection
    if (type === 'search-vehicle') {
        if (sections.vehicleSearchSection) {
            sections.vehicleSearchSection.style.display = 'block';
            console.log('Showing vehicle search section');
        }
    } else if (type === 'register-vehicle') {
        if (sections.newVehicleForm) {
            sections.newVehicleForm.style.display = 'block';
            console.log('Showing new vehicle form');
        }
    } else if (type === 'items-only') {
        if (sections.itemsOnlyCustomerSection) {
            sections.itemsOnlyCustomerSection.style.display = 'block';
            console.log('Showing items only customer section');
        }
        // Update progress indicator to skip vehicle step
        updateProgressForItemsOnly();
    }
    
    console.log('selectOrderType completed successfully');
}

function updateProgressForItemsOnly() {
    // Update step labels for items-only flow
    if (orderType === 'items-only') {
        const step1Label = document.querySelector('#step1-indicator .progress-label');
        const step2Label = document.querySelector('#step2-indicator .progress-label');
        const step3Label = document.querySelector('#step3-indicator .progress-label');
        const step4Indicator = document.querySelector('#step4-indicator');
        
        if (step1Label) step1Label.textContent = 'Customer';
        if (step2Label) step2Label.textContent = 'Items';
        if (step3Label) step3Label.textContent = 'Review';
        if (step4Indicator) step4Indicator.style.display = 'none';
    } else {
        // Restore original labels
        const step1Label = document.querySelector('#step1-indicator .progress-label');
        const step2Label = document.querySelector('#step2-indicator .progress-label');
        const step3Label = document.querySelector('#step3-indicator .progress-label');
        const step4Indicator = document.querySelector('#step4-indicator');
        
        if (step1Label) step1Label.textContent = 'Vehicle';
        if (step2Label) step2Label.textContent = 'Customer';
        if (step3Label) step3Label.textContent = 'Services';
        if (step4Indicator) {
            step4Indicator.style.display = 'block';
            const step4Label = step4Indicator.querySelector('.progress-label');
            if (step4Label) step4Label.textContent = 'Review';
        }
    }
}

function selectItemsOnlyCustomerType(type) {
    // Hide all customer sections first
    const sections = ['itemsOnlyCustomerSearch', 'itemsOnlyCustomerRegister', 'itemsOnlyWalkinSelected'];
    sections.forEach(sectionId => {
        const section = document.getElementById(sectionId);
        if (section) section.style.display = 'none';
    });
    
    if (type === 'search') {
        const searchSection = document.getElementById('itemsOnlyCustomerSearch');
        if (searchSection) searchSection.style.display = 'block';
    } else if (type === 'register') {
        const registerSection = document.getElementById('itemsOnlyCustomerRegister');
        if (registerSection) registerSection.style.display = 'block';
    } else if (type === 'walkin') {
        const walkinSection = document.getElementById('itemsOnlyWalkinSelected');
        if (walkinSection) walkinSection.style.display = 'block';
        // Set walk-in customer automatically
        selectedCustomer = { id: null, name: 'Walk-in Customer', phone: '', customerId: 'WALKIN' };
        const walkInField = document.getElementById('isWalkInCustomer');
        if (walkInField) walkInField.value = 'true';
    }
}

function searchItemsOnlyCustomers() {
    const query = document.getElementById('itemsOnlyCustomerSearchInput').value.trim();
    const resultsContainer = document.getElementById('itemsOnlyCustomerSearchResults');
    
    if (query.length < 2) {
        resultsContainer.style.display = 'none';
        return;
    }
    
    resultsContainer.innerHTML = '<div class="text-center p-3"><i class="fas fa-spinner fa-spin"></i> Searching...</div>';
    resultsContainer.style.display = 'block';
    
    // Get tenant slug from URL or global variable
    const pathParts = window.location.pathname.split('/');
    const tenantSlug = pathParts[2]; // Assuming URL structure /business/{tenant_slug}/...
    
    fetch(`/business/${tenantSlug}/services/ajax/customer/search/?q=${encodeURIComponent(query)}`, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        displayItemsOnlyCustomerResults(data.customers || []);
    })
    .catch(error => {
        console.error('Search error:', error);
        resultsContainer.innerHTML = '<div class="text-danger p-3">Error searching customers</div>';
    });
}

function displayItemsOnlyCustomerResults(customers) {
    const resultsContainer = document.getElementById('itemsOnlyCustomerSearchResults');
    
    if (customers.length === 0) {
        resultsContainer.innerHTML = '<div class="text-muted p-3">No customers found</div>';
        return;
    }
    
    let html = '';
    customers.forEach(customer => {
        html += `
            <div class="search-result-item" onclick="selectItemsOnlyCustomer('${customer.id}', '${customer.full_name}', '${customer.phone}', '${customer.customer_id}')">
                <div class="d-flex justify-content-between">
                    <div>
                        <strong>${customer.full_name}</strong>
                        <br><small>${customer.phone || 'No phone'}</small>
                    </div>
                    <div class="text-end">
                        <small class="text-muted">${customer.customer_id}</small>
                    </div>
                </div>
            </div>
        `;
    });
    
    resultsContainer.innerHTML = html;
}

function selectItemsOnlyCustomer(id, name, phone, customerId) {
    selectedCustomer = { id, name, phone, customerId };
    const selectedCustomerField = document.getElementById('selectedCustomerId');
    if (selectedCustomerField) selectedCustomerField.value = id;
    
    const searchResults = document.getElementById('itemsOnlyCustomerSearchResults');
    const searchInput = document.getElementById('itemsOnlyCustomerSearchInput');
    
    if (searchResults) searchResults.style.display = 'none';
    if (searchInput) searchInput.value = '';
    
    // Show success message
    console.log('Customer selected:', name);
}

// Step Management
function nextStep() {
    if (validateCurrentStep()) {
        if (orderType === 'items-only') {
            // Items-only flow: Step 1 (Customer) -> Step 2 (Items) -> Step 3 (Review)
            if (currentStep === 1) {
                currentStep = 3; // Skip to services/items step
            } else if (currentStep === 3) {
                currentStep = 4; // Go to review
            }
        } else {
            // Normal flow: Step 1 (Vehicle) -> Step 2 (Customer) -> Step 3 (Services) -> Step 4 (Review)
            if (currentStep < 4) {
                currentStep++;
            }
        }
        
        showStep(currentStep);
        updateStepIndicator();
        updateNavigationButtons();
    }
}

function previousStep() {
    if (orderType === 'items-only') {
        // Items-only flow backwards
        if (currentStep === 4) {
            currentStep = 3; // Review to Items
        } else if (currentStep === 3) {
            currentStep = 1; // Items to Customer
        }
    } else {
        // Normal flow backwards
        if (currentStep > 1) {
            currentStep--;
        }
    }
    
    showStep(currentStep);
    updateStepIndicator();
    updateNavigationButtons();
}

function showStep(step) {
    // Hide all steps
    document.querySelectorAll('.step-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Show current step
    const currentStepElement = document.getElementById(`step${step}`);
    if (currentStepElement) {
        currentStepElement.classList.add('active');
    }
    
    // Update step-specific content
    if (step === 2) {
        updateCustomerStep(); // Now step 2 is customer step
    } else if (step === 4) {
        updateReviewStep();
    }
}

function updateStepIndicator() {
    // Handle items-only flow differently
    if (orderType === 'items-only') {
        // Step mapping for items-only: 1=Customer, 3=Items, 4=Review
        const stepMap = { 1: 1, 3: 2, 4: 3 };
        const currentMappedStep = stepMap[currentStep] || 1;
        
        const currentStepNumber = document.getElementById('currentStepNumber');
        if (currentStepNumber) currentStepNumber.textContent = currentMappedStep;
        
        // Update indicators for 3-step flow
        for (let i = 1; i <= 3; i++) {
            const indicator = document.getElementById(`step${i}-indicator`);
            if (!indicator) continue;
            
            if (i < currentMappedStep) {
                indicator.classList.add('completed');
                indicator.classList.remove('active');
            } else if (i === currentMappedStep) {
                indicator.classList.add('active');
                indicator.classList.remove('completed');
            } else {
                indicator.classList.remove('active', 'completed');
            }
        }
        // Hide step 4 indicator for items-only
        const step4Indicator = document.getElementById('step4-indicator');
        if (step4Indicator) step4Indicator.style.display = 'none';
    } else {
        // Normal 4-step flow
        const currentStepNumber = document.getElementById('currentStepNumber');
        if (currentStepNumber) currentStepNumber.textContent = currentStep;
        
        const step4Indicator = document.getElementById('step4-indicator');
        if (step4Indicator) step4Indicator.style.display = 'flex';
        
        for (let i = 1; i <= 4; i++) {
            const indicator = document.getElementById(`step${i}-indicator`);
            if (!indicator) continue;
            
            if (i < currentStep) {
                indicator.classList.add('completed');
                indicator.classList.remove('active');
            } else if (i === currentStep) {
                indicator.classList.add('active');
                indicator.classList.remove('completed');
            } else {
                indicator.classList.remove('active', 'completed');
            }
        }
    }
}

function updateNavigationButtons() {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const submitBtn = document.getElementById('submitBtn');
    
    if (orderType === 'items-only') {
        // Show/hide previous button (hide on first step)
        if (prevBtn) prevBtn.style.display = currentStep === 1 ? 'none' : 'inline-flex';
        
        // Show next or submit button (submit on step 4/review)
        if (currentStep === 4) {
            if (nextBtn) nextBtn.style.display = 'none';
            if (submitBtn) submitBtn.style.display = 'inline-flex';
        } else {
            if (nextBtn) nextBtn.style.display = 'inline-flex';
            if (submitBtn) submitBtn.style.display = 'none';
        }
    } else {
        // Normal flow
        // Show/hide previous button
        if (prevBtn) prevBtn.style.display = currentStep > 1 ? 'inline-flex' : 'none';
        
        // Show next or submit button
        if (currentStep === 4) {
            if (nextBtn) nextBtn.style.display = 'none';
            if (submitBtn) submitBtn.style.display = 'inline-flex';
        } else {
            if (nextBtn) nextBtn.style.display = 'inline-flex';
            if (submitBtn) submitBtn.style.display = 'none';
        }
    }
}

function validateCurrentStep() {
    switch (currentStep) {
        case 1:
            return validateVehicleStep();
        case 2:
            return validateCustomerStep();
        case 3:
            return validateServicesStep();
        case 4:
            return true; // Review step doesn't need validation
        default:
            return true;
    }
}

function validateVehicleStep() {
    // For items-only orders, check if customer is selected
    if (orderType === 'items-only') {
        if (!selectedCustomer) {
            showToast('Please select a customer option for items-only sale', 'error');
            return false;
        }
        
        // If registering a new customer, validate the form
        const registerSection = document.getElementById('itemsOnlyCustomerRegister');
        if (registerSection && registerSection.style.display === 'block') {
            const name = document.getElementById('itemsOnlyCustomerName')?.value.trim();
            const phone = document.getElementById('itemsOnlyCustomerPhone')?.value.trim();
            
            if (!name || !phone) {
                showToast('Please enter customer name and phone number', 'error');
                return false;
            }
            
            // Create customer object for items-only registration
            selectedCustomer = {
                id: null,
                name: name,
                phone: phone,
                customerId: 'NEW',
                email: document.getElementById('itemsOnlyCustomerEmail')?.value.trim()
            };
        }
        return true;
    }
    
    // For vehicle orders, validate vehicle selection or registration
    if (selectedVehicle) {
        return true;
    }
    
    // Validate new vehicle form - only registration is required
    const registration = document.getElementById('vehicleRegistration')?.value.trim();
    
    if (!registration) {
        showToast('Please enter vehicle registration number', 'error');
        return false;
    }
    
    return true;
}

function validateCustomerStep() {
    // Implementation for customer step validation
    return true;
}

function validateServicesStep() {
    // Implementation for services step validation
    return true;
}

function updateCustomerStep() {
    // Implementation for updating customer step
}

function updateReviewStep() {
    // Implementation for updating review step
}

function showToast(message, type = 'info') {
    // Simple toast implementation
    alert(message); // Replace with proper toast later
}

// Utility function to get CSRF cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    updateStepIndicator();
    console.log('Quick Order JavaScript initialized');
});
