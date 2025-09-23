// Quick Order JavaScript
// Manages a multi-step quick order process for vehicle services and inventory items

// Get tenant slug from page URL or data attribute
let tenantSlug = '';

// Extract tenant slug from current URL
function getTenantSlug() {
    if (tenantSlug) return tenantSlug;
    
    const pathParts = window.location.pathname.split('/');
    const businessIndex = pathParts.indexOf('business');
    if (businessIndex !== -1 && pathParts[businessIndex + 1]) {
        tenantSlug = pathParts[businessIndex + 1];
        return tenantSlug;
    }
    
    // Fallback: get from meta tag if available
    const metaTag = document.querySelector('meta[name="tenant-slug"]');
    if (metaTag) {
        tenantSlug = metaTag.getAttribute('content');
        return tenantSlug;
    }
    
    return '';
}

let currentStep = 1;
let selectedCustomer = null;
let selectedVehicle = null;
let vehicleCustomer = null; // Customer from selected vehicle
let selectedServices = [];
let selectedPackage = null;
let selectedInventoryItems = []; // Initialize inventory items array
let selectedCustomerParts = []; // Initialize customer parts array
let allServices = [];
let serviceType = 'individual'; // 'individual', 'package', 'inventory', or 'customerParts'

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadAllServices();
    updateStepIndicator();
    initializeServiceSearch();
    initializePackageSearch();
    initializeInventorySearch();
    initializeGlobalSearch();
    initializePagination();
    initializeMobileSummary();
    updateCustomerPartsDisplay();
    
    // Add Enter key support for customer parts
    const customerPartName = document.getElementById('customerPartName');
    if (customerPartName) {
        customerPartName.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                addCustomerPart();
            }
        });
    }
    
    // Close price edit when clicking outside
    document.addEventListener('click', function(e) {
        if (currentPriceEdit && !e.target.closest('.price-edit-container')) {
            cancelPriceEdit();
        }
    });
});

// Function to toggle vehicle registration section
function toggleVehicleSkip() {
    const skipBtn = document.getElementById('skipVehicleBtn');
    const skipCheckbox = document.getElementById('skipVehicleCheckbox');
    const vehicleSection = document.getElementById('vehicleRegistrationSection');
    const skipVehicleInput = document.getElementById('skipVehicleInput');
    const btnText = document.getElementById('skipVehicleBtnText');
    
    const isCurrentlySkipped = skipCheckbox.value === 'true';
    
    if (!isCurrentlySkipped) {
        // Enable skip mode
        skipCheckbox.value = 'true';
        skipVehicleInput.value = 'true';
        vehicleSection.style.display = 'none';
        skipBtn.className = 'btn btn-success btn-lg';
        btnText.innerHTML = 'Vehicle Registration Skipped<br><small>Click to enable vehicle registration</small>';
        skipBtn.querySelector('i').className = 'fas fa-check me-2';
        
        // Clear any selected vehicle data
        selectedVehicle = null;
        selectedCustomer = null;
        selectedCustomerType = null;
        document.getElementById('selectedVehicleId').value = '';
        // Clear customer type radio buttons
        const radios = document.querySelectorAll('input[name="customer_type"]');
        radios.forEach(radio => radio.checked = false);
        
        // Clear services and packages since they need vehicles
        selectedServices = [];
        selectedPackage = null;
        document.querySelectorAll('.service-card').forEach(card => {
            card.classList.remove('selected');
        });
        document.querySelectorAll('.package-card').forEach(card => {
            card.classList.remove('selected');
        });
        
        // Automatically set to walk-in customer
        document.getElementById('isWalkInCustomer').value = 'true';
        
        // Switch to inventory tab
        showServiceType('inventory');
        
        showToast('Vehicle registration skipped. You can now sell inventory items only.', 'info');
    } else {
        // Disable skip mode
        skipCheckbox.value = 'false';
        skipVehicleInput.value = 'false';
        vehicleSection.style.display = 'block';
        skipBtn.className = 'btn btn-warning btn-lg';
        btnText.innerHTML = 'Skip Vehicle Registration<br><small>For inventory items only</small>';
        skipBtn.querySelector('i').className = 'fas fa-forward me-2';
        
        // Reset walk-in customer setting
        document.getElementById('isWalkInCustomer').value = 'false';
        
        // Switch back to individual services tab
        showServiceType('individual');
        
        showToast('Vehicle registration enabled. You can now register vehicles for services.', 'info');
    }
    
    validateCurrentStep();
}

// Step Management
function nextStep() {
    if (validateCurrentStep()) {
        if (currentStep < 4) {
            currentStep++;
            showStep(currentStep);
            updateStepIndicator();
            updateNavigationButtons();
        }
    }
}

function previousStep() {
    if (currentStep > 1) {
        currentStep--;
        showStep(currentStep);
        updateStepIndicator();
        updateNavigationButtons();
    }
}

function showStep(step) {
    // Hide all steps
    document.querySelectorAll('.step-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Show current step
    document.getElementById(`step${step}`).classList.add('active');
    
    // Update step-specific content
    if (step === 2) {
        updateCustomerStep(); // Now step 2 is customer step
    } else if (step === 4) {
        updateReviewStep();
    }
}

function updateStepIndicator() {
    document.getElementById('currentStepNumber').textContent = currentStep;
    
    // Update progress indicators
    for (let i = 1; i <= 4; i++) {
        const indicator = document.getElementById(`step${i}-indicator`);
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

function updateNavigationButtons() {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const submitBtn = document.getElementById('submitBtn');
    
    // Show/hide previous button
    prevBtn.style.display = currentStep > 1 ? 'inline-flex' : 'none';
    
    // Show next or submit button
    if (currentStep === 4) {
        nextBtn.style.display = 'none';
        submitBtn.style.display = 'inline-flex';
    } else {
        nextBtn.style.display = 'inline-flex';
        submitBtn.style.display = 'none';
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

// Customer Management
function searchCustomers() {
    const query = document.getElementById('customerSearchInput').value.trim();
    const resultsContainer = document.getElementById('customerSearchResults');
    
    if (query.length < 2) {
        resultsContainer.style.display = 'none';
        return;
    }
    
    resultsContainer.innerHTML = '<div class="text-center p-3"><i class="fas fa-spinner fa-spin"></i> Searching...</div>';
    resultsContainer.style.display = 'block';
    
    fetch(`/business/${getTenantSlug()}/services/ajax/customer/search/?q=${encodeURIComponent(query)}`, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        displayCustomerResults(data.customers || []);
    })
    .catch(error => {
        console.error('Search error:', error);
        resultsContainer.innerHTML = '<div class="text-danger p-3">Error searching customers</div>';
    });
}

function displayCustomerResults(customers) {
    const resultsContainer = document.getElementById('customerSearchResults');
    
    if (customers.length === 0) {
        resultsContainer.innerHTML = '<div class="text-muted p-3">No customers found</div>';
        return;
    }
    
    let html = '';
    customers.forEach(customer => {
        html += `
            <div class="search-result-item" onclick="selectCustomer('${customer.id}', '${customer.full_name}', '${customer.phone}', '${customer.customer_id}')">
                <div class="d-flex justify-content-between">
                    <div>
                        <strong>${customer.full_name}</strong>
                        <br><small>${customer.phone || 'No phone'}</small>
                    </div>
                    <div class="text-end">
                        <small class="text-muted">${customer.customer_id}</small>
                        <br><small>${customer.vehicle_count || 0} vehicle(s)</small>
                    </div>
                </div>
            </div>
        `;
    });
    
    resultsContainer.innerHTML = html;
}

function selectCustomer(id, name, phone, customerId) {
    selectedCustomer = { id, name, phone, customerId };
    
    // Update UI
    document.getElementById('selectedCustomerId').value = id;
    document.getElementById('selectedCustomerInfo').innerHTML = `
        <strong>${name}</strong><br>
        <small>Phone: ${phone}</small><br>
        <small>ID: ${customerId}</small>
    `;
    
    // Show selected customer, hide search and new customer form
    document.getElementById('selectedCustomerDisplay').style.display = 'block';
    document.getElementById('customerSearchResults').style.display = 'none';
    document.getElementById('newCustomerForm').style.display = 'none';
    
    // Clear search input
    document.getElementById('customerSearchInput').value = '';
}

function changeCustomer() {
    selectedCustomer = null;
    document.getElementById('selectedCustomerId').value = '';
    document.getElementById('selectedCustomerDisplay').style.display = 'none';
    document.getElementById('newCustomerForm').style.display = 'block';
    
    // Clear form fields
    document.getElementById('customerName').value = '';
    document.getElementById('customerPhone').value = '';
    document.getElementById('customerEmail').value = '';
}

// Vehicle Management (Step 1)
function searchVehiclesByRegistration() {
    const query = document.getElementById('vehicleSearchInput').value.trim();
    const resultsContainer = document.getElementById('vehicleSearchResults');
    
    if (query.length < 2) {
        resultsContainer.style.display = 'none';
        return;
    }
    
    resultsContainer.innerHTML = '<div class="text-center p-3"><i class="fas fa-spinner fa-spin"></i> Searching...</div>';
    resultsContainer.style.display = 'block';
    
    fetch(`/business/${getTenantSlug()}/services/ajax/vehicle/search/?q=${encodeURIComponent(query)}`, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        displayVehicleResults(data.results || []);
    })
    .catch(error => {
        console.error('Vehicle search error:', error);
        resultsContainer.innerHTML = '<div class="text-danger p-3">Error searching vehicles</div>';
    });
}

function displayVehicleResults(vehicles) {
    const resultsContainer = document.getElementById('vehicleSearchResults');
    
    if (vehicles.length === 0) {
        resultsContainer.innerHTML = '<div class="text-muted p-3">No vehicles found with this registration</div>';
        return;
    }
    
    let html = '';
    vehicles.forEach(vehicle => {
        html += `
            <div class="search-result-item" onclick="selectExistingVehicle('${vehicle.id}', '${vehicle.registration}', '${vehicle.make}', '${vehicle.model}', '${vehicle.color}', '${vehicle.customer_name}')">
                <div class="d-flex justify-content-between">
                    <div>
                        <strong>${vehicle.registration}</strong>
                        <br><small>${vehicle.make} ${vehicle.model}</small>
                    </div>
                    <div class="text-end">
                        <small class="text-muted">${vehicle.color}</small>
                        <br><small>Owner: ${vehicle.customer_name}</small>
                    </div>
                </div>
            </div>
        `;
    });
    
    resultsContainer.innerHTML = html;
}

function selectExistingVehicle(id, registration, make, model, color, customerName) {
    console.log('selectExistingVehicle called with:', { id, registration, make, model, color, customerName });
    
    selectedVehicle = { id, registration, make, model, color, customerName };
    
    // Update vehicle UI
    document.getElementById('selectedVehicleId').value = id;
    document.getElementById('selectedVehicleInfo').innerHTML = `
        <strong>${registration}</strong><br>
        <small>${make} ${model}</small><br>
        <small>Color: ${color}</small><br>
        <small>Owner: ${customerName}</small>
    `;
    
    // Show selected vehicle, hide search and new vehicle form
    document.getElementById('selectedVehicleDisplay').style.display = 'block';
    document.getElementById('vehicleSearchResults').style.display = 'none';
    document.getElementById('newVehicleForm').style.display = 'none';
    
    // Load vehicle's customer info for step 2
    console.log('Calling loadVehicleCustomer with auto-advance = true');
    loadVehicleCustomer(id, true); // Pass true to auto-advance
    
    // Clear search input
    document.getElementById('vehicleSearchInput').value = '';
}

function loadVehicleCustomer(vehicleId, autoAdvance = false) {
    console.log('loadVehicleCustomer called with vehicleId:', vehicleId, 'autoAdvance:', autoAdvance);
    
    // This will load the customer details when we move to step 2
    fetch(`/business/${getTenantSlug()}/customers/ajax/vehicle-customer/?vehicle_id=${vehicleId}`, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log('Vehicle customer response:', data);
        
        if (data.success && data.customer) {
            // Set both variables to ensure validation works
            vehicleCustomer = data.customer;
            selectedCustomer = data.customer;
            
            console.log('Loaded vehicle customer:', data.customer);
            
            // Check if customer is walk-in
            const isWalkInCustomer = data.customer.is_walk_in;
            
            // Pre-fill customer information
            document.getElementById('selectedCustomerId').value = data.customer.id;
            document.getElementById('isWalkInCustomer').value = isWalkInCustomer ? 'true' : 'false';
            
            console.log('Set customer form values:', {
                selectedCustomerId: data.customer.id,
                isWalkInCustomer: isWalkInCustomer ? 'true' : 'false'
            });
            
            // Hide all other customer options and show vehicle customer display
            document.getElementById('walkInCustomerDisplay').style.display = 'none';
            document.getElementById('selectedCustomerDisplay').style.display = 'none';
            document.getElementById('newCustomerForm').style.display = 'none';
            document.getElementById('customerSearchSection').style.display = 'none';
            document.getElementById('vehicleCustomerDisplay').style.display = 'block';
            
            let customerInfoHtml = '';
            if (isWalkInCustomer) {
                customerInfoHtml = `
                    <div class="alert alert-warning">
                        <i class="fas fa-walking me-2"></i>
                        <strong>Walk-in Customer:</strong> ${data.customer.full_name || 'Unknown'}<br>
                        <small>Phone: ${data.customer.phone || 'Not provided'}</small><br>
                        <small>Customer ID: ${data.customer.customer_id}</small><br>
                        <small class="text-muted">Previous walk-in customer</small>
                    </div>
                `;
                
                // Check for transaction details and ask to save if needed
                checkWalkInCustomerTransactions(data.customer.id);
            } else {
                customerInfoHtml = `
                    <div class="alert alert-info">
                        <i class="fas fa-car me-2"></i>
                        <strong>Vehicle Owner:</strong> ${data.customer.full_name}<br>
                        <small>Phone: ${data.customer.phone}</small><br>
                        <small>Customer ID: ${data.customer.customer_id}</small>
                    </div>
                `;
            }
            
            const vehicleCustomerInfoElement = document.getElementById('vehicleCustomerInfo');
            if (vehicleCustomerInfoElement) {
                vehicleCustomerInfoElement.innerHTML = customerInfoHtml;
            } else {
                console.error('vehicleCustomerInfo element not found');
            }
            
            // If auto-advance is enabled, automatically go to next step
            if (autoAdvance) {
                console.log('Starting auto-advance for vehicle customer, is walk-in:', isWalkInCustomer);
                console.log('Current step before auto-advance:', currentStep);
                
                // For vehicle with customer (walk-in or regular), skip customer step and go directly to services
                setTimeout(() => {
                    console.log('Auto-advancing directly to services step, skipping customer selection');
                    console.log('Setting currentStep from', currentStep, 'to 3');
                    currentStep = 3; // Skip customer step, go directly to services
                    
                    // Mark step 2 as completed since we have a customer
                    const step2Indicator = document.getElementById('step2-indicator');
                    if (step2Indicator) {
                        step2Indicator.classList.add('completed');
                        step2Indicator.classList.remove('active');
                        console.log('Marked step 2 as completed');
                    }
                    
                    console.log('Calling showStep(3)');
                    showStep(currentStep);
                    console.log('Calling updateStepIndicator()');
                    updateStepIndicator();
                    console.log('Calling updateNavigationButtons()');
                    updateNavigationButtons();
                    console.log('Auto-advance complete, currentStep is now:', currentStep);
                }, 300);
            } else {
                console.log('Auto-advance is disabled or no customer found');
            }
        }
    })
    .catch(error => {
        console.error('Error loading vehicle customer:', error);
    });
}

function changeVehicle() {
    selectedVehicle = null;
    vehicleCustomer = null;
    document.getElementById('selectedVehicleId').value = '';
    document.getElementById('selectedVehicleDisplay').style.display = 'none';
    document.getElementById('newVehicleForm').style.display = 'block';
    
    // Clear form fields
    document.getElementById('vehicleRegistration').value = '';
    document.getElementById('vehicleMake').value = '';
    document.getElementById('vehicleModel').value = '';
    document.getElementById('vehicleColor').value = '';
    document.getElementById('vehicleYear').value = '2020';
    document.getElementById('vehicleType').value = '';
}

function validateVehicleStep() {
    // Check if vehicle skip is enabled
    const skipVehicleCheckbox = document.getElementById('skipVehicleCheckbox');
    const skipVehicle = skipVehicleCheckbox && skipVehicleCheckbox.value === 'true';
    
    if (skipVehicle) {
        // Vehicle skip is enabled - check if only inventory items are selected
        const hasServices = selectedServices.length > 0;
        const hasPackage = selectedPackage !== null;
        
        if (hasServices || hasPackage) {
            showToast('Cannot skip vehicle registration when services are selected. Please unselect services or enable vehicle registration.', 'error');
            return false;
        }
        return true; // Skip vehicle validation for inventory-only orders
    }
    
    if (selectedVehicle) {
        return true;
    }
    
    // Validate new vehicle form - only registration is required
    const registration = document.getElementById('vehicleRegistration').value.trim();
    
    if (!registration) {
        showToast('Please enter vehicle registration number', 'error');
        return false;
    }
    
    return true;
}

// Customer Management (Step 2)
function selectWalkInCustomer() {
    selectedCustomer = null;
    document.getElementById('isWalkInCustomer').value = 'true';
    document.getElementById('selectedCustomerId').value = '';
    
    // Show walk-in display, hide other options
    document.getElementById('walkInCustomerDisplay').style.display = 'block';
    document.getElementById('selectedCustomerDisplay').style.display = 'none';
    document.getElementById('newCustomerForm').style.display = 'none';
    document.getElementById('customerSearchSection').style.display = 'none';
    document.getElementById('vehicleCustomerDisplay').style.display = 'none';
}

function showCustomerOptions() {
    document.getElementById('walkInCustomerDisplay').style.display = 'none';
    document.getElementById('vehicleCustomerDisplay').style.display = 'none';
    document.getElementById('customerSearchSection').style.display = 'block';
    document.getElementById('newCustomerForm').style.display = 'block';
}

function useVehicleCustomer() {
    if (vehicleCustomer) {
        selectedCustomer = vehicleCustomer;
        document.getElementById('selectedCustomerId').value = vehicleCustomer.id;
        document.getElementById('isWalkInCustomer').value = 'false';
        
        document.getElementById('selectedCustomerInfo').innerHTML = `
            <strong>${vehicleCustomer.name}</strong><br>
            <small>Phone: ${vehicleCustomer.phone}</small><br>
            <small>ID: ${vehicleCustomer.customer_id}</small>
        `;
        
        document.getElementById('selectedCustomerDisplay').style.display = 'block';
        document.getElementById('vehicleCustomerDisplay').style.display = 'none';
        document.getElementById('customerSearchSection').style.display = 'none';
        document.getElementById('newCustomerForm').style.display = 'none';
        document.getElementById('walkInCustomerDisplay').style.display = 'none';
    }
}

function updateCustomerStep() {
    // Show vehicle customer option if we have one
    if (selectedVehicle && vehicleCustomer) {
        const vehicleCustomerInfoElement = document.getElementById('vehicleCustomerInfo');
        if (vehicleCustomerInfoElement) {
            vehicleCustomerInfoElement.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-car me-2"></i>
                    <strong>Vehicle Owner:</strong> ${vehicleCustomer.full_name || vehicleCustomer.name}<br>
                    <small>Phone: ${vehicleCustomer.phone}</small><br>
                    <small>Customer ID: ${vehicleCustomer.customer_id}</small>
                </div>
            `;
        } else {
            console.error('vehicleCustomerInfo element not found in updateCustomerStep');
        }
        
        // Hide other options and show vehicle customer
        document.getElementById('walkInCustomerDisplay').style.display = 'none';
        document.getElementById('selectedCustomerDisplay').style.display = 'none';
        document.getElementById('newCustomerForm').style.display = 'none';
        document.getElementById('customerSearchSection').style.display = 'none';
        document.getElementById('vehicleCustomerDisplay').style.display = 'block';
    } else {
        document.getElementById('vehicleCustomerDisplay').style.display = 'none';
        // Show customer search and walk-in options by default
        document.getElementById('customerSearchSection').style.display = 'block';
        document.getElementById('newCustomerForm').style.display = 'block';
    }
}

function searchCustomers() {
    const query = document.getElementById('customerSearchInput').value.trim();
    const resultsContainer = document.getElementById('customerSearchResults');
    
    if (query.length < 2) {
        resultsContainer.style.display = 'none';
        return;
    }
    
    resultsContainer.innerHTML = '<div class="text-center p-3"><i class="fas fa-spinner fa-spin"></i> Searching...</div>';
    resultsContainer.style.display = 'block';
    
    fetch(`/business/${getTenantSlug()}/services/ajax/customer/search/?q=${encodeURIComponent(query)}`, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        displayCustomerResults(data.customers || []);
    })
    .catch(error => {
        console.error('Search error:', error);
        resultsContainer.innerHTML = '<div class="text-danger p-3">Error searching customers</div>';
    });
}

function displayCustomerResults(customers) {
    const resultsContainer = document.getElementById('customerSearchResults');
    
    if (customers.length === 0) {
        resultsContainer.innerHTML = '<div class="text-muted p-3">No customers found</div>';
        return;
    }
    
    let html = '';
    customers.forEach(customer => {
        html += `
            <div class="search-result-item" onclick="selectCustomer('${customer.id}', '${customer.full_name}', '${customer.phone}', '${customer.customer_id}')">
                <div class="d-flex justify-content-between">
                    <div>
                        <strong>${customer.full_name}</strong>
                        <br><small>${customer.phone || 'No phone'}</small>
                    </div>
                    <div class="text-end">
                        <small class="text-muted">${customer.customer_id}</small>
                        <br><small>${customer.vehicle_count || 0} vehicle(s)</small>
                    </div>
                </div>
            </div>
        `;
    });
    
    resultsContainer.innerHTML = html;
}

function selectCustomer(id, name, phone, customerId) {
    selectedCustomer = { id, name, phone, customerId };
    document.getElementById('isWalkInCustomer').value = 'false';
    
    // Update UI
    document.getElementById('selectedCustomerId').value = id;
    document.getElementById('selectedCustomerInfo').innerHTML = `
        <strong>${name}</strong><br>
        <small>Phone: ${phone}</small><br>
        <small>ID: ${customerId}</small>
    `;
    
    // Show selected customer, hide other options
    document.getElementById('selectedCustomerDisplay').style.display = 'block';
    document.getElementById('customerSearchResults').style.display = 'none';
    document.getElementById('newCustomerForm').style.display = 'none';
    document.getElementById('walkInCustomerDisplay').style.display = 'none';
    document.getElementById('vehicleCustomerDisplay').style.display = 'none';
    
    // Clear search input
    document.getElementById('customerSearchInput').value = '';
}

function changeCustomer() {
    selectedCustomer = null;
    document.getElementById('selectedCustomerId').value = '';
    document.getElementById('isWalkInCustomer').value = 'false';
    document.getElementById('selectedCustomerDisplay').style.display = 'none';
    
    // Show customer options again
    showCustomerOptions();
    
    // Clear form fields
    document.getElementById('customerName').value = '';
    document.getElementById('customerPhone').value = '';
    document.getElementById('customerEmail').value = '';
}

function validateCustomerStep() {
    const isWalkIn = document.getElementById('isWalkInCustomer').value === 'true';
    
    // Check if vehicle skip is enabled
    const skipVehicleCheckbox = document.getElementById('skipVehicleCheckbox');
    const skipVehicle = skipVehicleCheckbox && skipVehicleCheckbox.value === 'true';
    
    // Debug logging
    console.log('Validating customer step:', {
        isWalkIn,
        skipVehicle,
        selectedCustomer: !!selectedCustomer,
        vehicleCustomer: !!vehicleCustomer,
        selectedCustomerId: selectedCustomer?.id,
        vehicleCustomerId: vehicleCustomer?.id
    });
    
    // If skipping vehicle, automatically use walk-in customer
    if (skipVehicle) {
        document.getElementById('isWalkInCustomer').value = 'true';
        console.log('Customer step validation passed - vehicle skipped, using walk-in');
        return true;
    }
    
    if (isWalkIn || selectedCustomer || vehicleCustomer) {
        console.log('Customer step validation passed');
        return true;
    }
    
    // Check if customer form has data for new customer
    const name = document.getElementById('customerName').value.trim();
    const phone = document.getElementById('customerPhone').value.trim();
    
    // For new vehicle registration, at least one of name or phone should be provided
    if (!name && !phone) {
        console.log('Customer step validation failed: no customer details');
        showToast('Please provide customer details, select an existing customer, or choose walk-in', 'error');
        return false;
    }
    
    console.log('Customer step validation passed with form data');
    return true;
}

// Service Management
function showServiceType(type) {
    serviceType = type;
    
    // Update button states
    document.getElementById('individualServicesBtn').classList.toggle('active', type === 'individual');
    document.getElementById('packagesBtn').classList.toggle('active', type === 'packages');
    document.getElementById('inventoryBtn').classList.toggle('active', type === 'inventory');
    document.getElementById('customerPartsBtn').classList.toggle('active', type === 'customerParts');
    
    // Show/hide sections
    document.getElementById('individualServicesSection').style.display = type === 'individual' ? 'block' : 'none';
    document.getElementById('packagesSection').style.display = type === 'packages' ? 'block' : 'none';
    document.getElementById('inventorySection').style.display = type === 'inventory' ? 'block' : 'none';
    document.getElementById('customerPartsSection').style.display = type === 'customerParts' ? 'block' : 'none';
    
    // Clear section-specific searches when switching tabs
    if (type === 'individual') {
        clearPackageSearch();
        clearInventorySearch();
        clearCustomerPartsSearch();
        selectedPackage = null;
        selectedInventoryItems = [];
        selectedCustomerParts = [];
        document.querySelectorAll('.package-card').forEach(card => {
            card.classList.remove('selected');
        });
        document.querySelectorAll('.inventory-card').forEach(card => {
            card.classList.remove('selected');
        });
        document.querySelectorAll('.customer-part-card').forEach(card => {
            card.classList.remove('selected');
        });
    } else if (type === 'packages') {
        clearServiceSearch();
        clearInventorySearch();
        clearCustomerPartsSearch();
        selectedServices = [];
        selectedInventoryItems = [];
        selectedCustomerParts = [];
        document.querySelectorAll('.service-card').forEach(card => {
            card.classList.remove('selected');
        });
        document.querySelectorAll('.inventory-card').forEach(card => {
            card.classList.remove('selected');
        });
        document.querySelectorAll('.customer-part-card').forEach(card => {
            card.classList.remove('selected');
        });
    } else if (type === 'inventory') {
        clearServiceSearch();
        clearPackageSearch();
        clearCustomerPartsSearch();
        selectedServices = [];
        selectedPackage = null;
        selectedCustomerParts = [];
        document.querySelectorAll('.service-card').forEach(card => {
            card.classList.remove('selected');
        });
        document.querySelectorAll('.package-card').forEach(card => {
            card.classList.remove('selected');
        });
        document.querySelectorAll('.customer-part-card').forEach(card => {
            card.classList.remove('selected');
        });
    } else if (type === 'customerParts') {
        clearServiceSearch();
        clearPackageSearch();
        clearInventorySearch();
        selectedServices = [];
        selectedPackage = null;
        selectedInventoryItems = [];
        document.querySelectorAll('.service-card').forEach(card => {
            card.classList.remove('selected');
        });
        document.querySelectorAll('.package-card').forEach(card => {
            card.classList.remove('selected');
        });
        document.querySelectorAll('.inventory-card').forEach(card => {
            card.classList.remove('selected');
        });
        // Don't clear customer parts when switching to customer parts tab
        updateCustomerPartsDisplay();
    }
    
    updateOrderSummary();
}

function loadAllServices() {
    // Services are already loaded from the template
    // This function can be used to load additional services via AJAX if needed
}

function filterServices(categoryId) {
    // Update active category button
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-category="${categoryId}"]`).classList.add('active');
    
    // Filter service cards
    document.querySelectorAll('.service-card').forEach(card => {
        const cardCategory = card.dataset.category;
        if (categoryId === 'all' || cardCategory === categoryId) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
    
    // Clear search input when changing categories
    const searchInput = document.getElementById('serviceSearchInput');
    if (searchInput) {
        searchInput.value = '';
    }
}

// Service search functionality
function initializeServiceSearch() {
    const searchInput = document.getElementById('serviceSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase().trim();
            searchServices(searchTerm);
        });
    }
}

function searchServices(searchTerm) {
    const serviceCards = document.querySelectorAll('.service-card');
    let visibleCount = 0;
    
    serviceCards.forEach(card => {
        const serviceName = card.querySelector('.service-name').textContent.toLowerCase();
        const serviceDescription = card.querySelector('.service-description').textContent.toLowerCase();
        const serviceCategory = card.querySelector('.service-category').textContent.toLowerCase();
        
        const matches = searchTerm === '' || 
                       serviceName.includes(searchTerm) || 
                       serviceDescription.includes(searchTerm) ||
                       serviceCategory.includes(searchTerm);
        
        if (matches) {
            card.style.display = 'block';
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });
    
    // Show/hide empty state
    const servicesGrid = document.getElementById('servicesGrid');
    const existingEmptyState = servicesGrid.querySelector('.search-empty-state');
    
    if (visibleCount === 0 && searchTerm !== '') {
        if (!existingEmptyState) {
            const emptyState = document.createElement('div');
            emptyState.className = 'search-empty-state col-12 text-center py-4';
            emptyState.innerHTML = `
                <i class="fas fa-search text-muted mb-3" style="font-size: 2rem;"></i>
                <h6 class="text-muted">No services found</h6>
                <p class="text-muted small">Try different keywords or clear the search</p>
            `;
            servicesGrid.appendChild(emptyState);
        }
    } else if (existingEmptyState) {
        existingEmptyState.remove();
    }
    
    // Reset category filter to "All" when searching
    if (searchTerm !== '') {
        document.querySelectorAll('.category-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector('[data-category="all"]').classList.add('active');
    }
}

function clearServiceSearch() {
    const searchInput = document.getElementById('serviceSearchInput');
    if (searchInput) {
        searchInput.value = '';
        searchServices('');
    }
    
    // Remove empty state if it exists
    const existingEmptyState = document.querySelector('.search-empty-state');
    if (existingEmptyState) {
        existingEmptyState.remove();
    }
}

// Package search functionality
function initializePackageSearch() {
    const searchInput = document.getElementById('packageSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase().trim();
            searchPackages(searchTerm);
        });
    }
}

function searchPackages(searchTerm) {
    const packageCards = document.querySelectorAll('.package-card');
    let visibleCount = 0;
    
    packageCards.forEach(card => {
        const packageName = card.querySelector('.package-name').textContent.toLowerCase();
        const packageDescription = card.querySelector('.package-description').textContent.toLowerCase();
        
        const matches = searchTerm === '' || 
                       packageName.includes(searchTerm) || 
                       packageDescription.includes(searchTerm);
        
        if (matches) {
            card.style.display = 'block';
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });
    
    // Show/hide empty state
    const packagesGrid = document.getElementById('packagesGrid');
    const existingEmptyState = packagesGrid.querySelector('.search-empty-state');
    
    if (visibleCount === 0 && searchTerm !== '') {
        if (!existingEmptyState) {
            const emptyState = document.createElement('div');
            emptyState.className = 'search-empty-state col-12 text-center py-4';
            emptyState.innerHTML = `
                <i class="fas fa-search text-muted mb-3" style="font-size: 2rem;"></i>
                <h6 class="text-muted">No packages found</h6>
                <p class="text-muted small">Try different keywords or clear the search</p>
            `;
            packagesGrid.appendChild(emptyState);
        }
    } else if (existingEmptyState) {
        existingEmptyState.remove();
    }
}

function clearPackageSearch() {
    const searchInput = document.getElementById('packageSearchInput');
    if (searchInput) {
        searchInput.value = '';
        searchPackages('');
    }
    
    // Remove empty state if it exists
    const existingEmptyState = document.querySelector('#packagesGrid .search-empty-state');
    if (existingEmptyState) {
        existingEmptyState.remove();
    }
}

// Inventory search functionality
function initializeInventorySearch() {
    const searchInput = document.getElementById('inventorySearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase().trim();
            searchInventory(searchTerm);
        });
    }
}

function searchInventory(searchTerm) {
    const inventoryCards = document.querySelectorAll('.inventory-card');
    let visibleCount = 0;
    
    inventoryCards.forEach(card => {
        const itemName = card.querySelector('.service-name').textContent.toLowerCase();
        const itemDescription = card.querySelector('.service-description');
        const descriptionText = itemDescription ? itemDescription.textContent.toLowerCase() : '';
        
        const matches = searchTerm === '' || 
                       itemName.includes(searchTerm) || 
                       descriptionText.includes(searchTerm);
        
        if (matches) {
            card.style.display = 'block';
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });
    
    // Show/hide empty state
    const inventoryGrid = document.getElementById('inventoryGrid');
    const existingEmptyState = inventoryGrid.querySelector('.search-empty-state');
    
    if (visibleCount === 0 && searchTerm !== '') {
        if (!existingEmptyState) {
            const emptyState = document.createElement('div');
            emptyState.className = 'search-empty-state col-12 text-center py-4';
            emptyState.innerHTML = `
                <i class="fas fa-search text-muted mb-3" style="font-size: 2rem;"></i>
                <h6 class="text-muted">No inventory items found</h6>
                <p class="text-muted small">Try different keywords or clear the search</p>
            `;
            inventoryGrid.appendChild(emptyState);
        }
    } else if (existingEmptyState) {
        existingEmptyState.remove();
    }
    
    // Reset category filter to "All" when searching
    if (searchTerm !== '') {
        document.querySelectorAll('.inventory-category-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector('[data-inventory-category="all"]').classList.add('active');
    }
}

function clearInventorySearch() {
    const searchInput = document.getElementById('inventorySearchInput');
    if (searchInput) {
        searchInput.value = '';
        searchInventory('');
    }
    
    // Remove empty state if it exists
    const existingEmptyState = document.querySelector('#inventoryGrid .search-empty-state');
    if (existingEmptyState) {
        existingEmptyState.remove();
    }
}

function clearCustomerPartsSearch() {
    // Customer parts don't have a search function, but this function is called
    // We can use it to reset customer parts display if needed
    updateCustomerPartsDisplay();
}

// Global search functionality
function initializeGlobalSearch() {
    const searchInput = document.getElementById('globalSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase().trim();
            globalSearch(searchTerm);
        });
    }
}

function globalSearch(searchTerm) {
    // Search across all sections
    searchServices(searchTerm);
    searchPackages(searchTerm);
    searchInventory(searchTerm);
    
    // Clear section-specific search inputs
    const serviceSearchInput = document.getElementById('serviceSearchInput');
    const packageSearchInput = document.getElementById('packageSearchInput');
    const inventorySearchInput = document.getElementById('inventorySearchInput');
    
    if (serviceSearchInput) serviceSearchInput.value = '';
    if (packageSearchInput) packageSearchInput.value = '';
    if (inventorySearchInput) inventorySearchInput.value = '';
    
    // If searching, show results count in each tab
    if (searchTerm !== '') {
        updateTabResultCounts(searchTerm);
    } else {
        clearTabResultCounts();
    }
}

function updateTabResultCounts(searchTerm) {
    // Count visible items in each section
    const visibleServices = document.querySelectorAll('#servicesGrid .service-card[style*="block"], #servicesGrid .service-card:not([style*="none"])').length;
    const visiblePackages = document.querySelectorAll('#packagesGrid .package-card[style*="block"], #packagesGrid .package-card:not([style*="none"])').length;
    const visibleInventory = document.querySelectorAll('#inventoryGrid .inventory-card[style*="block"], #inventoryGrid .inventory-card:not([style*="none"])').length;
    
    // Update button text with counts
    const serviceBtn = document.getElementById('individualServicesBtn');
    const packageBtn = document.getElementById('packagesBtn');
    const inventoryBtn = document.getElementById('inventoryBtn');
    
    if (serviceBtn) {
        serviceBtn.innerHTML = `<i class="fas fa-list"></i> Individual Services (${visibleServices})`;
    }
    if (packageBtn) {
        packageBtn.innerHTML = `<i class="fas fa-box"></i> Service Packages (${visiblePackages})`;
    }
    if (inventoryBtn) {
        inventoryBtn.innerHTML = `<i class="fas fa-boxes"></i> Inventory Items (${visibleInventory})`;
    }
}

function clearTabResultCounts() {
    // Reset button text to original
    const serviceBtn = document.getElementById('individualServicesBtn');
    const packageBtn = document.getElementById('packagesBtn');
    const inventoryBtn = document.getElementById('inventoryBtn');
    
    if (serviceBtn) {
        serviceBtn.innerHTML = `<i class="fas fa-list"></i> Individual Services`;
    }
    if (packageBtn) {
        packageBtn.innerHTML = `<i class="fas fa-box"></i> Service Packages`;
    }
    if (inventoryBtn) {
        inventoryBtn.innerHTML = `<i class="fas fa-boxes"></i> Inventory Items`;
    }
}

function clearGlobalSearch() {
    const searchInput = document.getElementById('globalSearchInput');
    if (searchInput) {
        searchInput.value = '';
        globalSearch('');
    }
    
    // Clear all section searches too
    clearServiceSearch();
    clearPackageSearch();
    clearInventorySearch();
}

// Pagination functionality
let currentPages = {
    services: 1,
    packages: 1,
    inventory: 1
};

const itemsPerPage = {
    services: 6,
    packages: 4,
    inventory: 6
};

function initializePagination() {
    // Only show pagination on mobile
    if (window.innerWidth <= 768) {
        initializeServicesPagination();
        initializePackagesPagination();
        initializeInventoryPagination();
    }
    
    // Listen for window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth <= 768) {
            document.querySelectorAll('.pagination-container').forEach(container => {
                container.style.display = 'block';
            });
            updateAllPagination();
        } else {
            document.querySelectorAll('.pagination-container').forEach(container => {
                container.style.display = 'none';
            });
            showAllItems();
        }
    });
}

function initializeServicesPagination() {
    const serviceCards = document.querySelectorAll('#servicesGrid .service-card');
    const totalPages = Math.ceil(serviceCards.length / itemsPerPage.services);
    updatePaginationDisplay('services', serviceCards.length, totalPages);
    showServicesPage(1);
}

function initializePackagesPagination() {
    const packageCards = document.querySelectorAll('#packagesGrid .package-card');
    const totalPages = Math.ceil(packageCards.length / itemsPerPage.packages);
    updatePaginationDisplay('packages', packageCards.length, totalPages);
    showPackagesPage(1);
}

function initializeInventoryPagination() {
    const inventoryCards = document.querySelectorAll('#inventoryGrid .inventory-card');
    const totalPages = Math.ceil(inventoryCards.length / itemsPerPage.inventory);
    updatePaginationDisplay('inventory', inventoryCards.length, totalPages);
    showInventoryPage(1);
}

function showServicesPage(page) {
    const serviceCards = document.querySelectorAll('#servicesGrid .service-card');
    const totalPages = Math.ceil(serviceCards.length / itemsPerPage.services);
    
    if (page < 1) page = 1;
    if (page > totalPages) page = totalPages;
    
    currentPages.services = page;
    
    const startIndex = (page - 1) * itemsPerPage.services;
    const endIndex = startIndex + itemsPerPage.services;
    
    serviceCards.forEach((card, index) => {
        if (index >= startIndex && index < endIndex) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
    
    updatePaginationDisplay('services', serviceCards.length, totalPages);
}

function showPackagesPage(page) {
    const packageCards = document.querySelectorAll('#packagesGrid .package-card');
    const totalPages = Math.ceil(packageCards.length / itemsPerPage.packages);
    
    if (page < 1) page = 1;
    if (page > totalPages) page = totalPages;
    
    currentPages.packages = page;
    
    const startIndex = (page - 1) * itemsPerPage.packages;
    const endIndex = startIndex + itemsPerPage.packages;
    
    packageCards.forEach((card, index) => {
        if (index >= startIndex && index < endIndex) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
    
    updatePaginationDisplay('packages', packageCards.length, totalPages);
}

function showInventoryPage(page) {
    const inventoryCards = document.querySelectorAll('#inventoryGrid .inventory-card');
    const totalPages = Math.ceil(inventoryCards.length / itemsPerPage.inventory);
    
    if (page < 1) page = 1;
    if (page > totalPages) page = totalPages;
    
    currentPages.inventory = page;
    
    const startIndex = (page - 1) * itemsPerPage.inventory;
    const endIndex = startIndex + itemsPerPage.inventory;
    
    inventoryCards.forEach((card, index) => {
        if (index >= startIndex && index < endIndex) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
    
    updatePaginationDisplay('inventory', inventoryCards.length, totalPages);
}

function updatePaginationDisplay(section, totalItems, totalPages) {
    const infoElement = document.getElementById(`${section}PaginationInfo`);
    const pagesElement = document.getElementById(`${section}PaginationPages`);
    const prevBtn = document.getElementById(`${section}PrevBtn`);
    const nextBtn = document.getElementById(`${section}NextBtn`);
    
    if (infoElement && totalItems > 0) {
        const currentPage = currentPages[section];
        const startItem = (currentPage - 1) * itemsPerPage[section] + 1;
        const endItem = Math.min(currentPage * itemsPerPage[section], totalItems);
        
        infoElement.textContent = `Showing ${startItem}-${endItem} of ${totalItems} items`;
        
        if (pagesElement) {
            pagesElement.textContent = `Page ${currentPage} of ${totalPages}`;
        }
        
        if (prevBtn) {
            prevBtn.disabled = currentPage <= 1;
        }
        
        if (nextBtn) {
            nextBtn.disabled = currentPage >= totalPages;
        }
    }
}

function changeServicesPage(direction) {
    const newPage = currentPages.services + direction;
    showServicesPage(newPage);
}

function changePackagesPage(direction) {
    const newPage = currentPages.packages + direction;
    showPackagesPage(newPage);
}

function changeInventoryPage(direction) {
    const newPage = currentPages.inventory + direction;
    showInventoryPage(newPage);
}

function showAllItems() {
    // Show all items when not on mobile
    document.querySelectorAll('.service-card, .package-card, .inventory-card').forEach(card => {
        card.style.display = 'block';
    });
}

function updateAllPagination() {
    if (window.innerWidth <= 768) {
        initializeServicesPagination();
        initializePackagesPagination();
        initializeInventoryPagination();
    }
}

// Mobile summary functionality
function initializeMobileSummary() {
    // Update mobile summary when order changes
    updateMobileSummary();
    
    // Ensure mobile summary is visible on mobile devices
    const mobileOrderSummary = document.getElementById('mobileOrderSummary');
    if (mobileOrderSummary && window.innerWidth <= 768) {
        mobileOrderSummary.style.display = 'block';
    }
}

function toggleMobileSummary() {
    const content = document.getElementById('mobileSummaryContent');
    const icon = document.getElementById('mobileSummaryIcon');
    
    if (content.classList.contains('show')) {
        content.classList.remove('show');
        icon.className = 'fas fa-chevron-up';
    } else {
        content.classList.add('show');
        icon.className = 'fas fa-chevron-down';
    }
}

function updateMobileSummary() {
    // Update mobile summary with current selections
    const mobileTitle = document.getElementById('mobileSummaryTitle');
    const mobilePreview = document.getElementById('mobileSummaryPreview');
    const mobileTotalAmount = document.getElementById('mobileTotalAmount');
    const mobileSelectedServices = document.getElementById('mobileSelectedServices');
    const mobileSummaryTotals = document.getElementById('mobileSummaryTotals');
    
    const totalItems = selectedServices.length + (selectedPackage ? 1 : 0) + selectedInventoryItems.length + selectedCustomerParts.length;
    const totalAmount = calculateTotalAmount();
    
    if (totalItems > 0) {
        mobileTitle.textContent = `Order Summary (${totalItems} items)`;
        mobilePreview.textContent = `${totalItems} item${totalItems > 1 ? 's' : ''} selected`;
        mobileTotalAmount.textContent = `KES ${totalAmount.toFixed(2)}`;
        
        // Update detailed mobile summary
        updateMobileDetailedSummary();
        mobileSummaryTotals.style.display = 'block';
    } else {
        mobileTitle.textContent = 'Order Summary';
        mobilePreview.textContent = 'No items selected';
        mobileTotalAmount.textContent = 'KES 0';
        mobileSelectedServices.innerHTML = '<div class="text-muted text-center py-3">No items selected</div>';
        mobileSummaryTotals.style.display = 'none';
    }
}

function updateMobileDetailedSummary() {
    const container = document.getElementById('mobileSelectedServices');
    const subtotalElement = document.getElementById('mobileSubtotalAmount');
    const taxElement = document.getElementById('mobileTaxAmount');
    const totalElement = document.getElementById('mobileTotalAmountDetail');
    const durationElement = document.getElementById('mobileEstimatedDuration');
    
    let html = '';
    let subtotal = 0;
    let totalDuration = 0;
    
    // Add selected services
    selectedServices.forEach(service => {
        html += `
            <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
                <div>
                    <div class="fw-medium">${service.name}</div>
                    <small class="text-muted">${service.duration} min</small>
                </div>
                <div>KES ${service.price.toFixed(2)}</div>
            </div>
        `;
        subtotal += service.price;
        totalDuration += service.duration;
    });
    
    // Add selected package
    if (selectedPackage) {
        html += `
            <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
                <div>
                    <div class="fw-medium">${selectedPackage.name}</div>
                    <small class="text-muted">Package - ${selectedPackage.duration} min</small>
                </div>
                <div>KES ${selectedPackage.price.toFixed(2)}</div>
            </div>
        `;
        subtotal += selectedPackage.price;
        totalDuration += selectedPackage.duration;
    }
    
    // Add selected inventory items
    selectedInventoryItems.forEach(item => {
        html += `
            <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
                <div>
                    <div class="fw-medium">${item.name}</div>
                    <small class="text-muted">Qty: ${item.quantity}</small>
                </div>
                <div>KES ${(item.price * item.quantity).toFixed(2)}</div>
            </div>
        `;
        subtotal += item.price * item.quantity;
    });
    
    // Add selected customer parts (always free)
    selectedCustomerParts.forEach(part => {
        html += `
            <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
                <div>
                    <div class="fw-medium">
                        <i class="fas fa-gift text-success me-1"></i>
                        ${part.name}
                    </div>
                    <small class="text-muted">Qty: ${part.quantity} - Customer Part</small>
                </div>
                <div class="text-success">FREE</div>
            </div>
        `;
        // Customer parts don't add to subtotal
    });
    
    container.innerHTML = html;
    
    // Update totals - assume prices are VAT inclusive
    const totalVatInclusive = subtotal; // Subtotal already includes VAT
    const taxAmount = totalVatInclusive / 1.16 * 0.16; // Extract VAT amount
    const subtotalExVat = totalVatInclusive - taxAmount; // Ex-VAT amount
    
    if (subtotalElement) subtotalElement.textContent = `KES ${subtotalExVat.toFixed(2)}`;
    if (taxElement) taxElement.textContent = `KES ${taxAmount.toFixed(2)}`;
    if (totalElement) totalElement.textContent = `KES ${totalVatInclusive.toFixed(2)}`;
    if (durationElement) durationElement.textContent = totalDuration;
}

function calculateTotalAmount() {
    let total = 0;
    
    selectedServices.forEach(service => {
        total += service.price;
    });
    
    if (selectedPackage) {
        total += selectedPackage.price;
    }
    
    selectedInventoryItems.forEach(item => {
        total += item.price * item.quantity;
    });
    
    return total; // Prices are already VAT inclusive
}

function toggleService(serviceId) {
    // Check if vehicle skip is enabled
    const skipVehicleCheckbox = document.getElementById('skipVehicleCheckbox');
    const skipVehicle = skipVehicleCheckbox && skipVehicleCheckbox.value === 'true';
    
    const serviceCard = document.querySelector(`[data-service-id="${serviceId}"]`);
    const isSelected = serviceCard.classList.contains('selected');
    
    console.log('toggleService called for:', serviceId, 'currently selected:', isSelected);
    
    if (!isSelected && skipVehicle) {
        // Prevent selecting services when vehicle is skipped
        showToast('Cannot select services when vehicle registration is skipped. Enable vehicle registration or select inventory items only.', 'warning');
        return;
    }
    
    if (isSelected) {
        // Remove service
        serviceCard.classList.remove('selected');
        console.log('Removing service from selectedServices:', serviceId);
        selectedServices = selectedServices.filter(s => s.id !== serviceId);
    } else {
        // Add service
        serviceCard.classList.add('selected');
        
        // Get service data from the card
        const serviceName = serviceCard.querySelector('.service-name').textContent;
        const servicePriceText = serviceCard.querySelector('.service-price').textContent;
        const servicePrice = parseFloat(servicePriceText.replace(/[^0-9.]/g, ''));
        const serviceDuration = parseInt(serviceCard.querySelector('.service-duration').textContent);
        
        // Check if this service had a custom price before (from previous selection)
        const existingService = selectedServices.find(s => s.id === serviceId);
        let customPrice = existingService && existingService.customPrice ? existingService.customPrice : null;
        
        // Check for pending custom price (set before service was selected)
        if (!customPrice && window.pendingCustomPrices && window.pendingCustomPrices.services && window.pendingCustomPrices.services[serviceId]) {
            customPrice = window.pendingCustomPrices.services[serviceId];
            console.log('Found pending custom price for service:', serviceId, customPrice);
            // Clear the pending price since we're using it now
            delete window.pendingCustomPrices.services[serviceId];
        }
        
        const finalPrice = customPrice || servicePrice;
        
        console.log('Adding service to selectedServices:', serviceId, 'with custom price:', customPrice);
        selectedServices.push({
            id: serviceId,
            name: serviceName,
            price: finalPrice,
            duration: serviceDuration,
            customPrice: customPrice  // This will be sent to backend if set
        });
    }
    
    updateOrderSummary();
}

function togglePackage(packageId) {
    // Check if vehicle skip is enabled
    const skipVehicleCheckbox = document.getElementById('skipVehicleCheckbox');
    const skipVehicle = skipVehicleCheckbox && skipVehicleCheckbox.value === 'true';
    
    const packageCard = document.querySelector(`[data-package-id="${packageId}"]`);
    const isSelected = packageCard.classList.contains('selected');
    
    if (!isSelected && skipVehicle) {
        // Prevent selecting packages when vehicle is skipped
        showToast('Cannot select service packages when vehicle registration is skipped. Enable vehicle registration or select inventory items only.', 'warning');
        return;
    }
    
    // Clear all other package selections (only one package can be selected)
    document.querySelectorAll('.package-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    if (isSelected) {
        // Deselect package
        selectedPackage = null;
    } else {
        // Select package
        packageCard.classList.add('selected');
        
        // Get package data from the card
        const packageName = packageCard.querySelector('.package-name').textContent;
        const packagePriceText = packageCard.querySelector('.package-price').textContent;
        const packagePrice = parseFloat(packagePriceText.replace(/[^0-9.]/g, ''));
        const packageDuration = parseInt(packageCard.querySelector('.package-duration').textContent);
        const servicesCount = parseInt(packageCard.querySelector('.package-services-count').textContent);
        
        selectedPackage = {
            id: packageId,
            name: packageName,
            price: packagePrice,
            duration: packageDuration,
            servicesCount: servicesCount
        };
    }
    
    updateOrderSummary();
}

function clearAllServices() {
    selectedServices = [];
    selectedPackage = null;
    selectedInventoryItems = [];
    
    // Clear service selections
    document.querySelectorAll('.service-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Clear package selections
    document.querySelectorAll('.package-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Clear inventory selections and reset quantities
    document.querySelectorAll('.inventory-card').forEach(card => {
        card.classList.remove('selected');
        const quantityInput = card.querySelector('.inventory-quantity-input');
        if (quantityInput) {
            quantityInput.value = 0;
        }
    });
    
    updateOrderSummary();
}

// Review Step
function updateReviewStep() {
    // Update customer info - handle walk-in, selected, and vehicle customers
    let customerInfo = '';
    const isWalkIn = document.getElementById('isWalkInCustomer').value === 'true';
    
    if (isWalkIn) {
        customerInfo = `<div class="alert alert-warning"><i class="fas fa-walking me-2"></i><strong>Walk-in Customer</strong><br><small>No registration required</small></div>`;
    } else if (vehicleCustomer) {
        customerInfo = `<div class="alert alert-info"><i class="fas fa-car me-2"></i><strong>${vehicleCustomer.full_name || vehicleCustomer.name}</strong><br><small>Phone: ${vehicleCustomer.phone}</small><br><small>ID: ${vehicleCustomer.customer_id}</small><br><small class="text-muted">Vehicle Owner</small></div>`;
    } else if (selectedCustomer) {
        customerInfo = `<strong>${selectedCustomer.name}</strong><br><small>Phone: ${selectedCustomer.phone}</small><br><small>ID: ${selectedCustomer.customerId}</small>`;
    } else {
        const customerName = document.getElementById('customerName').value.trim();
        const customerPhone = document.getElementById('customerPhone').value.trim();
        if (customerName || customerPhone) {
            customerInfo = `<strong>${customerName || 'New Customer'}</strong><br><small>Phone: ${customerPhone || 'Not provided'}</small><br><small class="text-muted">New Registration</small>`;
        } else {
            customerInfo = `<div class="text-muted">No customer information</div>`;
        }
    }
    document.getElementById('reviewCustomerInfo').innerHTML = customerInfo;
    
    // Update vehicle info
    let vehicleInfo = '';
    if (selectedVehicle) {
        vehicleInfo = `<strong>${selectedVehicle.registration}</strong><br><small>${selectedVehicle.make} ${selectedVehicle.model}</small><br><small>Color: ${selectedVehicle.color}</small>`;
        if (selectedVehicle.customerName) {
            vehicleInfo += `<br><small class="text-muted">Owner: ${selectedVehicle.customerName}</small>`;
        }
    } else {
        const registration = document.getElementById('vehicleRegistration').value.trim();
        const make = document.getElementById('vehicleMake').value.trim();
        const model = document.getElementById('vehicleModel').value.trim();
        const color = document.getElementById('vehicleColor').value.trim();
        if (registration || make || model) {
            vehicleInfo = `<strong>${registration || 'New Vehicle'}</strong><br><small>${make} ${model}</small><br><small>Color: ${color}</small><br><small class="text-muted">New Registration</small>`;
        } else {
            vehicleInfo = `<div class="text-muted">No vehicle information</div>`;
        }
    }
    document.getElementById('reviewVehicleInfo').innerHTML = vehicleInfo;
    
    // Update services and inventory info
    let servicesHtml = '';
    let inventoryHtml = '';
    let totalInclusiveVAT = 0;
    let totalDuration = 0;
    
    // Show package if selected
    if (selectedPackage) {
        servicesHtml += `<div class="d-flex justify-content-between"><span><strong>${selectedPackage.name}</strong> (Package)</span><span>KES ${selectedPackage.price.toFixed(2)}</span></div>`;
        totalInclusiveVAT += selectedPackage.price;
        totalDuration += selectedPackage.duration;
    }
    
    // Show individual services if selected
    if (selectedServices && selectedServices.length > 0) {
        selectedServices.forEach(service => {
            servicesHtml += `<div class="d-flex justify-content-between"><span><i class="fas fa-tools me-2"></i>${service.name}</span><span>KES ${service.price.toFixed(2)}</span></div>`;
            totalInclusiveVAT += service.price;
            totalDuration += service.duration;
        });
    }
    
    // Show inventory items if selected
    if (selectedInventoryItems && selectedInventoryItems.length > 0) {
        selectedInventoryItems.forEach(item => {
            const itemTotal = item.price * item.quantity;
            inventoryHtml += `<div class="d-flex justify-content-between"><span><i class="fas fa-box me-2"></i>${item.name} (Qty: ${item.quantity})</span><span>KES ${itemTotal.toFixed(2)}</span></div>`;
            totalInclusiveVAT += itemTotal;
        });
    }
    
    // Show customer parts if selected (always free)
    if (selectedCustomerParts && selectedCustomerParts.length > 0) {
        selectedCustomerParts.forEach(part => {
            inventoryHtml += `<div class="d-flex justify-content-between"><span><i class="fas fa-gift text-success me-2"></i>${part.name} (Qty: ${part.quantity}) - Customer Part</span><span class="text-success">FREE</span></div>`;
            // Customer parts don't add to total
        });
    }
    
    // Update services section visibility and content
    const servicesSection = document.getElementById('reviewServicesSection');
    const servicesInfo = document.getElementById('reviewServicesInfo');
    if (servicesHtml) {
        servicesSection.style.display = 'block';
        servicesInfo.innerHTML = servicesHtml;
    } else {
        servicesSection.style.display = 'none';
    }
    
    // Update inventory section visibility and content
    const inventorySection = document.getElementById('reviewInventorySection');
    const inventoryInfo = document.getElementById('reviewInventoryInfo');
    if (inventoryHtml) {
        inventorySection.style.display = 'block';
        inventoryInfo.innerHTML = inventoryHtml;
        
        // Update section title if it includes customer parts
        const hasCustomerParts = selectedCustomerParts && selectedCustomerParts.length > 0;
        const hasInventoryItems = selectedInventoryItems && selectedInventoryItems.length > 0;
        const sectionTitle = document.querySelector('#reviewInventorySection h6');
        if (sectionTitle) {
            if (hasCustomerParts && hasInventoryItems) {
                sectionTitle.innerHTML = '<i class="fas fa-box me-2"></i>Inventory Items & Customer Parts';
            } else if (hasCustomerParts) {
                sectionTitle.innerHTML = '<i class="fas fa-gift me-2"></i>Customer Parts';
            } else {
                sectionTitle.innerHTML = '<i class="fas fa-box me-2"></i>Inventory Items';
            }
        }
    } else {
        inventorySection.style.display = 'none';
    }
    
    // Update total info with inclusive VAT
    if (totalInclusiveVAT > 0) {
        const taxAmount = totalInclusiveVAT / 1.16 * 0.16; // Extract VAT amount
        const subtotalExVAT = totalInclusiveVAT - taxAmount; // Ex-VAT amount
        
        document.getElementById('reviewTotalInfo').innerHTML = `
            <div class="d-flex justify-content-between"><span>Subtotal (ex VAT):</span><span>KES ${subtotalExVAT.toFixed(2)}</span></div>
            <div class="d-flex justify-content-between"><span>VAT (16%):</span><span>KES ${taxAmount.toFixed(2)}</span></div>
            <hr>
            <div class="d-flex justify-content-between"><strong><span>Total (incl VAT):</span><span>KES ${totalInclusiveVAT.toFixed(2)}</span></strong></div>
            <div class="d-flex justify-content-between text-muted"><small><span>Estimated Duration:</span><span>${totalDuration} minutes</span></small></div>
        `;
    } else {
        document.getElementById('reviewTotalInfo').innerHTML = '<div class="text-muted">No items selected</div>';
    }
}

// Form Submission
function submitOrder() {
    // Validate that we have all required data
    if (!validateAllSteps()) {
        showToast('Please complete all required fields', 'error');
        return;
    }
    
    const form = document.getElementById('quickOrderForm');
    const submitBtn = document.getElementById('submitBtn');
    const originalText = submitBtn.innerHTML;
    
    // Show loading state
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating Order...';
    submitBtn.disabled = true;
    
    try {
        // Prepare form data
        const formData = new FormData();
        
        // Add CSRF token with multiple fallbacks
        const csrfToken = getCSRFToken();
        if (!csrfToken) {
            throw new Error('CSRF token not found. Please refresh the page.');
        }
        
        console.log('Using CSRF token:', csrfToken.substring(0, 10) + '...');
        
        // Check if vehicle skip is enabled
        const skipVehicleCheckbox = document.getElementById('skipVehicleCheckbox');
        const skipVehicle = skipVehicleCheckbox && skipVehicleCheckbox.value === 'true';
        
        // Add skip vehicle flag
        formData.set('skip_vehicle', skipVehicle ? 'true' : 'false');
        
        // Vehicle data (only if not skipping vehicle)
        if (!skipVehicle) {
            if (selectedVehicle) {
                formData.set('selected_vehicle_id', selectedVehicle.id);
            } else {
                const vehicleRegistration = document.getElementById('vehicleRegistration').value.trim().toUpperCase();
                const vehicleMake = document.getElementById('vehicleMake').value.trim();
                const vehicleModel = document.getElementById('vehicleModel').value.trim();
                const vehicleColor = document.getElementById('vehicleColor').value.trim();
                const vehicleType = document.getElementById('vehicleType').value;
                const vehicleYear = document.getElementById('vehicleYear').value;
                
                if (!vehicleRegistration) {
                    throw new Error('Vehicle registration number is required');
                }
                
                formData.set('vehicle_registration', vehicleRegistration);
                formData.set('vehicle_make', vehicleMake || 'Unknown');
                formData.set('vehicle_model', vehicleModel || 'Unknown');
                formData.set('vehicle_color', vehicleColor || 'Unknown');
                formData.set('vehicle_type', vehicleType || 'car');
                formData.set('vehicle_year', vehicleYear || '2020');
            }
        }

        // Customer data (automatically set to walk-in if vehicle is skipped)
        const isWalkIn = skipVehicle ? true : (document.getElementById('isWalkInCustomer').value === 'true');
        formData.set('is_walk_in_customer', isWalkIn);
        
        if (!skipVehicle && selectedCustomer) {
            formData.set('selected_customer_id', selectedCustomer.id);
        } else if (!skipVehicle && !isWalkIn) {
            const customerName = document.getElementById('customerName').value.trim();
            const customerPhone = document.getElementById('customerPhone').value.trim();
            const customerEmail = document.getElementById('customerEmail').value.trim();
            
            if (customerName || customerPhone) {
                formData.set('customer_name', customerName);
                formData.set('customer_phone', customerPhone);
                formData.set('customer_email', customerEmail);
                
                // Check if vehicle should be added to customer
                if (document.getElementById('addVehicleToCustomer').checked) {
                    formData.set('add_vehicle_to_customer', 'on');
                }
            }
        }
        
        // Service selection data
        const selectedServicesDataElement = document.getElementById('selectedServicesData');
        const selectedServicesDataValue = selectedServicesDataElement ? selectedServicesDataElement.value : '';
        console.log('Raw selectedServicesData value:', selectedServicesDataValue);
        console.log('Current selectedServices array at submission:', JSON.stringify(selectedServices, null, 2));
        
        const selectionData = JSON.parse(selectedServicesDataValue || '{}');
        console.log('Parsed selection data:', selectionData);
        console.log('Services custom prices in selectionData:', selectionData.services_custom_prices);
        
        if (selectionData.type === 'package' && selectionData.package_id) {
            formData.set('service_type', 'package');
            formData.set('selected_package', selectionData.package_id);
        } else if (selectionData.type === 'individual' && selectionData.service_ids && selectionData.service_ids.length > 0) {
            formData.set('service_type', 'individual');
            selectionData.service_ids.forEach(serviceId => {
                formData.append('selected_services', serviceId);
            });
            // Add custom prices if they exist
            if (selectionData.services_custom_prices) {
                formData.set('services_custom_prices', JSON.stringify(selectionData.services_custom_prices));
            }
        } else if (selectionData.type === 'inventory' && selectionData.inventory_items && selectionData.inventory_items.length > 0) {
            formData.set('service_type', 'inventory');
            selectionData.inventory_items.forEach(item => {
                formData.append('selected_inventory_items', item.id);
                formData.append(`inventory_quantity_${item.id}`, item.quantity);
            });
            // Add custom prices for inventory items
            const inventoryCustomPrices = {};
            selectionData.inventory_items.forEach(item => {
                if (item.custom_price) {
                    inventoryCustomPrices[item.id] = item.custom_price;
                }
            });
            if (Object.keys(inventoryCustomPrices).length > 0) {
                formData.set('inventory_custom_prices', JSON.stringify(inventoryCustomPrices));
            }
        } else if (selectionData.type === 'mixed') {
            formData.set('service_type', 'mixed');
            if (selectionData.service_ids && selectionData.service_ids.length > 0) {
                selectionData.service_ids.forEach(serviceId => {
                    formData.append('selected_services', serviceId);
                });
                // Add custom prices for services
                if (selectionData.services_custom_prices) {
                    formData.set('services_custom_prices', JSON.stringify(selectionData.services_custom_prices));
                }
            }
            if (selectionData.inventory_items && selectionData.inventory_items.length > 0) {
                selectionData.inventory_items.forEach(item => {
                    formData.append('selected_inventory_items', item.id);
                    formData.append(`inventory_quantity_${item.id}`, item.quantity);
                });
                // Add custom prices for inventory items
                const inventoryCustomPrices = {};
                selectionData.inventory_items.forEach(item => {
                    if (item.custom_price) {
                        inventoryCustomPrices[item.id] = item.custom_price;
                    }
                });
                if (Object.keys(inventoryCustomPrices).length > 0) {
                    formData.set('inventory_custom_prices', JSON.stringify(inventoryCustomPrices));
                }
            }
            // Add customer parts
            if (selectionData.customer_parts && selectionData.customer_parts.length > 0) {
                formData.set('customer_parts', JSON.stringify(selectionData.customer_parts));
            }
        } else if (selectionData.type === 'package' && selectionData.package_id) {
            formData.set('service_type', 'package');
            formData.set('selected_package', selectionData.package_id);
            // Add custom price for package
            if (selectionData.custom_price) {
                formData.set('package_custom_price', selectionData.custom_price);
            }
        } else {
            throw new Error('Please select at least one service, package, or inventory item');
        }
        
        // Additional order details
        formData.set('special_instructions', document.getElementById('specialInstructions').value.trim());
        formData.set('priority', document.getElementById('priority').value);
        
        // Log the data being sent (for debugging)
        console.log('Submitting order with data:', Object.fromEntries(formData.entries()));
        
        // Function to make the actual request
        const makeRequest = (token) => {
            return fetch(window.location.href, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': token,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'  // Important for CSRF
            });
        };
        
        // Make the request with CSRF retry logic
        makeRequest(csrfToken)
        .then(async (response) => {
            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);
            
            // If CSRF failure, try to refresh token and retry once
            if (response.status === 403) {
                const responseText = await response.text();
                if (responseText.includes('CSRF') || responseText.includes('csrf')) {
                    console.log('CSRF error detected, attempting to refresh token...');
                    try {
                        const newToken = await refreshCSRFToken();
                        if (newToken) {
                            // Update formData with new token
                            formData.set('csrfmiddlewaretoken', newToken);
                            console.log('Retrying request with new CSRF token...');
                            return makeRequest(newToken);
                        }
                    } catch (refreshError) {
                        console.error('Failed to refresh CSRF token:', refreshError);
                        throw new Error('CSRF token expired. Please refresh the page and try again.');
                    }
                }
            }
            
            return response;
        })
        .then(response => {
            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);
            
            // Check if response is ok
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Check if response is JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new Error('Server did not return JSON response');
            }
            
            return response.json();
        })
        .then(data => {
            console.log('Response data:', data);
            
            if (data.success) {
                showToast('Order created successfully!', 'success');
                
                // Start checking payment status for walk-in customers with M-Pesa
                if (data.order_id) {
                    checkPaymentStatus(data.order_id);
                }
                
                // Redirect after a short delay
                setTimeout(() => {
                    if (data.redirect_url) {
                        window.location.href = data.redirect_url;
                    } else {
                        // Fallback redirect
                        window.location.href = `/business/${getTenantSlug()}/services/orders/${data.order_id}/`;
                    }
                }, 1500);
            } else {
                // Handle server-side validation errors
                showToast(data.message || 'Error creating order', 'error');
                
                // Show field-specific errors if available
                if (data.errors) {
                    console.log('Form errors:', data.errors);
                    displayFormErrors(data.errors);
                }
            }
        })
        .catch(error => {
            console.error('Order creation error:', error);
            
            let errorMessage = 'Error creating order. Please try again.';
            
            if (error.message.includes('CSRF') || error.message.includes('csrf')) {
                errorMessage = 'Security token expired. Please refresh the page and try again.';
                // Add a refresh button to the error message
                showToast(`${errorMessage} <button onclick="window.location.reload()" class="btn btn-sm btn-outline-light ms-2">Refresh Page</button>`, 'error');
                return; // Don't show the generic toast
            } else if (error.message.includes('HTTP 500')) {
                errorMessage = 'Server error. Please contact support if this persists.';
            } else if (error.message.includes('HTTP 403')) {
                errorMessage = 'Access denied. Please check your permissions and try again.';
            } else if (error.message.includes('HTTP 404')) {
                errorMessage = 'Service not found. Please refresh the page.';
            } else if (error.message.includes('Network')) {
                errorMessage = 'Network error. Please check your connection.';
            }
            
            showToast(errorMessage, 'error');
        })
        .finally(() => {
            // Restore button state
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        });
        
    } catch (error) {
        console.error('Form preparation error:', error);
        showToast(error.message || 'Error preparing order data', 'error');
        
        // Restore button state
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

function validateAllSteps() {
    // Check if vehicle skip is enabled
    const skipVehicleCheckbox = document.getElementById('skipVehicleCheckbox');
    const skipVehicle = skipVehicleCheckbox && skipVehicleCheckbox.value === 'true';
    
    console.log('validateAllSteps debug:', {
        skipVehicle,
        selectedPackage: !!selectedPackage,
        selectedServices: selectedServices.length,
        selectedInventoryItems: selectedInventoryItems.length,
        selectedServicesData: document.getElementById('selectedServicesData').value
    });
    
    // If skipping vehicle, validate that only inventory items are selected
    if (skipVehicle) {
        const hasServices = selectedServices.length > 0;
        const hasPackage = selectedPackage !== null;
        const hasInventoryItems = selectedInventoryItems.length > 0;
        
        if (hasServices || hasPackage) {
            console.log('Validation failed: services selected but vehicle skipped');
            return false;
        }
        
        if (!hasInventoryItems) {
            console.log('Validation failed: no inventory items selected');
            return false;
        }
        
        console.log('Vehicle skipped - inventory-only validation passed');
        return true;
    }
    
    // Vehicle not skipped - normal validation
    
    // Validate customer - check if walk-in is selected or vehicle customer is loaded
    const isWalkIn = document.getElementById('isWalkInCustomer').value === 'true';
    
    if (!isWalkIn && !selectedCustomer && !vehicleCustomer) {
        const name = document.getElementById('customerName').value.trim();
        const phone = document.getElementById('customerPhone').value.trim();
        if (!name || !phone) {
            console.log('Validation failed: customer info missing');
            return false;
        }
    }
    
    // Validate vehicle - only registration is required
    if (!selectedVehicle) {
        const registration = document.getElementById('vehicleRegistration').value.trim();
        
        if (!registration) {
            console.log('Validation failed: vehicle registration missing');
            return false;
        }
    }
    
    // Validate services/items
    const hasPackage = selectedPackage !== null;
    const hasServices = selectedServices.length > 0;
    const hasInventoryItems = selectedInventoryItems.length > 0;
    
    if (!hasPackage && !hasServices && !hasInventoryItems) {
        console.log('Validation failed: no selections made');
        return false;
    }
    
    console.log('All validations passed');
    return true;
}

function displayFormErrors(errors) {
    // Clear previous errors
    document.querySelectorAll('.form-control').forEach(field => {
        field.classList.remove('is-invalid');
    });
    document.querySelectorAll('.invalid-feedback').forEach(el => el.remove());
    
    // Display new errors
    Object.keys(errors).forEach(fieldName => {
        const fieldErrors = errors[fieldName];
        if (fieldErrors && fieldErrors.length > 0) {
            // Try to find the form field
            let field = document.querySelector(`[name="${fieldName}"]`);
            if (!field) {
                // Try alternative field names
                const fieldMappings = {
                    'customer_name': 'customerName',
                    'customer_phone': 'customerPhone',
                    'vehicle_registration': 'vehicleRegistration',
                    'vehicle_make': 'vehicleMake',
                    'vehicle_model': 'vehicleModel',
                    'vehicle_color': 'vehicleColor',
                    'vehicle_type': 'vehicleType'
                };
                field = document.getElementById(fieldMappings[fieldName]);
            }
            
            if (field) {
                field.classList.add('is-invalid');
                
                // Add error message
                const errorDiv = document.createElement('div');
                errorDiv.className = 'invalid-feedback';
                errorDiv.textContent = fieldErrors[0];
                field.parentNode.appendChild(errorDiv);
            }
        }
    });
}

// Enhanced CSRF token getter with multiple fallbacks
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

// Robust CSRF token getter with multiple fallbacks and refresh capability
function getCSRFToken() {
    // First, try to get from form
    const formToken = document.querySelector('[name=csrfmiddlewaretoken]');
    if (formToken && formToken.value) {
        console.log('CSRF token from form:', formToken.value.substring(0, 10) + '...');
        return formToken.value;
    }
    
    // Second, try to get from cookie
    const cookieToken = getCookie('csrftoken') || getCookie('autowash_csrftoken');
    if (cookieToken) {
        console.log('CSRF token from cookie:', cookieToken.substring(0, 10) + '...');
        return cookieToken;
    }
    
    // Third, try meta tag
    const metaToken = document.querySelector('meta[name="csrf-token"]');
    if (metaToken) {
        console.log('CSRF token from meta:', metaToken.getAttribute('content').substring(0, 10) + '...');
        return metaToken.getAttribute('content');
    }
    
    console.error('No CSRF token found in form, cookie, or meta tag');
    return null;
}

// Function to refresh CSRF token
function refreshCSRFToken() {
    return fetch(window.location.href, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.text())
    .then(html => {
        // Extract new CSRF token from response
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const newToken = doc.querySelector('[name=csrfmiddlewaretoken]');
        
        if (newToken) {
            // Update form token
            const currentFormToken = document.querySelector('[name=csrfmiddlewaretoken]');
            if (currentFormToken) {
                currentFormToken.value = newToken.value;
                console.log('CSRF token refreshed');
                return newToken.value;
            }
        }
        throw new Error('Could not refresh CSRF token');
    });
}

// Initialize page and token refresh
document.addEventListener('DOMContentLoaded', function() {
    console.log('Quick Order form initialized');
    
    // Check CSRF token on page load
    const initialToken = getCSRFToken();
    if (!initialToken) {
        console.warn('No CSRF token found on page load');
        showToast('Security token missing. Please refresh the page.', 'warning');
    } else {
        console.log('Initial CSRF token verified');
    }
    
    // Refresh CSRF token every 10 minutes to prevent expiry
    setInterval(() => {
        refreshCSRFToken().then(() => {
            console.log('CSRF token auto-refreshed');
        }).catch(error => {
            console.warn('Auto CSRF refresh failed:', error);
        });
    }, 600000); // 10 minutes
    
    // Also refresh token when page becomes visible again (user returns to tab)
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            refreshCSRFToken().then(() => {
                console.log('CSRF token refreshed on page focus');
            }).catch(error => {
                console.warn('CSRF refresh on focus failed:', error);
            });
        }
    });
});

// Enhanced toast with better positioning and styling
function showToast(message, type) {
    // Remove existing toasts
    document.querySelectorAll('.toast-notification').forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    
    const iconMap = {
        'success': 'check-circle',
        'error': 'exclamation-triangle',
        'warning': 'exclamation-circle',
        'info': 'info-circle'
    };
    
    const colorMap = {
        'success': '#10b981',
        'error': '#ef4444',
        'warning': '#f59e0b',
        'info': '#06b6d4'
    };
    
    toast.innerHTML = `
        <div class="toast-content">
            <i class="fas fa-${iconMap[type] || 'info-circle'}"></i>
            <span>${message}</span>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // Apply styles
    toast.style.cssText = `
        position: fixed;
        top: 2rem;
        right: 2rem;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 0.75rem;
        padding: 1rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        z-index: 9999;
        min-width: 300px;
        max-width: 500px;
        animation: slideInRight 0.3s ease-out;
        border-left: 4px solid ${colorMap[type] || colorMap.info};
    `;
    
    const content = toast.querySelector('.toast-content');
    content.style.cssText = `
        display: flex;
        align-items: center;
        gap: 0.75rem;
        color: #374151;
    `;
    
    const icon = content.querySelector('i');
    icon.style.color = colorMap[type] || colorMap.info;
    
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.style.cssText = `
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        background: none;
        border: none;
        color: #9ca3af;
        cursor: pointer;
        padding: 0.25rem;
        border-radius: 0.375rem;
        transition: color 0.15s ease-in-out;
    `;
    
    closeBtn.addEventListener('mouseenter', () => {
        closeBtn.style.color = '#374151';
    });
    
    closeBtn.addEventListener('mouseleave', () => {
        closeBtn.style.color = '#9ca3af';
    });
    
    document.body.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.animation = 'slideOutRight 0.3s ease-in';
            setTimeout(() => toast.remove(), 300);
        }
    }, 5000);
}

// Add CSS animations
if (!document.getElementById('toast-animations')) {
    const style = document.createElement('style');
    style.id = 'toast-animations';
    style.textContent = `
        @keyframes slideInRight {
            from { opacity: 0; transform: translateX(100%); }
            to { opacity: 1; transform: translateX(0); }
        }
        @keyframes slideOutRight {
            from { opacity: 1; transform: translateX(0); }
            to { opacity: 0; transform: translateX(100%); }
        }
        .invalid-feedback {
            display: block;
            width: 100%;
            margin-top: 0.25rem;
            font-size: 0.875rem;
            color: #ef4444;
        }
        .form-control.is-invalid {
            border-color: #ef4444;
            box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
        }
    `;
    document.head.appendChild(style);
}
// Auto-search as user types
document.getElementById('customerSearchInput').addEventListener('input', function() {
    clearTimeout(this.searchTimeout);
    this.searchTimeout = setTimeout(() => {
        if (this.value.length >= 2) {
            searchCustomers();
        }
    }, 300);
});

document.getElementById('vehicleSearchInput').addEventListener('input', function() {
    clearTimeout(this.searchTimeout);
    this.searchTimeout = setTimeout(() => {
        if (this.value.length >= 2) {
            searchVehiclesByRegistration();
        } else {
            document.getElementById('vehicleSearchResults').style.display = 'none';
        }
    }, 300);
});

// Phone number formatting
document.getElementById('customerPhone').addEventListener('input', function(e) {
    let value = e.target.value.replace(/\D/g, '');
    
    if (value.startsWith('0')) {
        value = '254' + value.substring(1);
    }
    if (value.startsWith('254') && !value.startsWith('+254')) {
        value = '+' + value;
    }
    
    e.target.value = value;
});

// Registration number formatting
document.getElementById('vehicleRegistration').addEventListener('input', function(e) {
    e.target.value = e.target.value.toUpperCase();
});

// Utility functions
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

function showToast(message, type) {
    // Remove existing toasts
    document.querySelectorAll('.toast-notification').forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.innerHTML = `
        <div class="toast-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-triangle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // Toast styles
    toast.style.cssText = `
        position: fixed;
        top: 2rem;
        right: 2rem;
        background: white;
        border: 1px solid var(--gray-200);
        border-radius: var(--radius-lg);
        padding: 1rem;
        box-shadow: var(--shadow-lg);
        z-index: 9999;
        min-width: 300px;
        animation: slideInRight 0.3s ease-out;
        border-left: 4px solid ${type === 'success' ? 'var(--success-500)' : type === 'error' ? '#ef4444' : 'var(--info-500)'};
    `;
    
    const content = toast.querySelector('.toast-content');
    content.style.cssText = `
        display: flex;
        align-items: center;
        gap: 0.75rem;
    `;
    
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.style.cssText = `
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        background: none;
        border: none;
        color: var(--gray-400);
        cursor: pointer;
        padding: 0.25rem;
        border-radius: var(--radius-sm);
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 5000);
}

// Check for walk-in customer transaction details
function checkWalkInCustomerTransactions(customerId) {
    // Check if this walk-in customer has recent M-Pesa transactions that could be saved
    fetch(`/business/${getTenantSlug()}/customers/ajax/check-walk-in-transactions/?customer_id=${customerId}`, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && data.has_transactions) {
            // Show notification that customer has transaction details available
            showToast(`This walk-in customer has transaction details available. Consider saving their information.`, 'info');
            
            // Optional: Show save suggestion modal if there are recent payments
            if (data.recent_payment) {
                setTimeout(() => {
                    showCustomerSaveModal({
                        payment_id: data.recent_payment.id,
                        customer_phone: data.recent_payment.customer_phone,
                        amount: data.recent_payment.amount
                    });
                }, 2000);
            }
        }
    })
    .catch(error => {
        console.error('Error checking walk-in customer transactions:', error);
    });
}

// Customer Save Notification Functions
function showCustomerSaveModal(paymentData) {
    // Populate transaction details
    const detailsDiv = document.getElementById('transactionCustomerDetails');
    detailsDiv.innerHTML = `
        <div><strong>Phone:</strong> ${paymentData.customer_phone || 'N/A'}</div>
        <div><strong>Amount:</strong> KSh ${paymentData.amount || 'N/A'}</div>
        <div><strong>Transaction:</strong> ${paymentData.payment_id || 'N/A'}</div>
    `;
    
    // Store payment ID for save action
    document.getElementById('saveCustomerBtn').setAttribute('data-payment-id', paymentData.payment_id);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('customerSaveModal'));
    modal.show();
}

// Handle save customer button click
document.getElementById('saveCustomerBtn').addEventListener('click', function() {
    const paymentId = this.getAttribute('data-payment-id');
    if (paymentId) {
        // Redirect to save customer page
        window.location.href = `/customers/save-walk-in/${paymentId}/`;
    }
});

// Function to check for payment completion and show notification
function checkPaymentStatus(orderId) {
    if (!orderId) return;
    
    // Poll for payment completion every 3 seconds
    const checkInterval = setInterval(() => {
        fetch(`/business/${getTenantSlug()}/payments/ajax/status/?order_id=${orderId}`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.payment) {
                if (data.payment.status === 'completed' && data.payment.method === 'mpesa') {
                    // Check if customer is walk-in
                    if (data.payment.customer_is_walk_in && data.payment.customer_phone) {
                        clearInterval(checkInterval);
                        showCustomerSaveModal({
                            payment_id: data.payment.id,
                            customer_phone: data.payment.customer_phone,
                            amount: data.payment.amount
                        });
                    }
                } else if (data.payment.status === 'failed') {
                    clearInterval(checkInterval);
                    showToast('Payment failed. Please try again.', 'error');
                }
            }
        })
        .catch(error => {
            console.error('Error checking payment status:', error);
        });
    }, 3000);
    
    // Stop checking after 5 minutes
    setTimeout(() => {
        clearInterval(checkInterval);
    }, 300000);
}

// Inventory Functions
function showServiceType(type) {
    serviceType = type;
    
    // Update button states
    document.getElementById('individualServicesBtn').classList.toggle('active', type === 'individual');
    document.getElementById('packagesBtn').classList.toggle('active', type === 'packages');
    document.getElementById('inventoryBtn').classList.toggle('active', type === 'inventory');
    document.getElementById('customerPartsBtn').classList.toggle('active', type === 'customerParts');
    
    // Show/hide sections
    document.getElementById('individualServicesSection').style.display = type === 'individual' ? 'block' : 'none';
    document.getElementById('packagesSection').style.display = type === 'packages' ? 'block' : 'none';
    document.getElementById('inventorySection').style.display = type === 'inventory' ? 'block' : 'none';
    document.getElementById('customerPartsSection').style.display = type === 'customerParts' ? 'block' : 'none';
    
    // Don't clear selections - just maintain current state
    // Users should be able to switch between tabs and keep their selections
    
    updateOrderSummary();
}

function filterInventoryItems(categoryId) {
    // Update active category button
    document.querySelectorAll('.inventory-category-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-inventory-category="${categoryId}"]`).classList.add('active');
    
    // Filter inventory cards
    document.querySelectorAll('.inventory-card').forEach(card => {
        const cardCategory = card.dataset.category;
        if (categoryId === 'all' || cardCategory === categoryId) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
    
    // Clear search input when changing categories
    const searchInput = document.getElementById('inventorySearchInput');
    if (searchInput) {
        searchInput.value = '';
    }
}

function selectInventoryCard(itemId) {
    const itemCard = document.querySelector(`[data-item-id="${itemId}"]`);
    const quantityInput = itemCard.querySelector('.inventory-quantity-input');
    const maxStock = parseFloat(quantityInput.dataset.maxStock) || 0;
    
    // Don't allow selection if out of stock
    if (maxStock === 0) {
        showToast('This item is out of stock', 'warning');
        return;
    }
    
    const currentQuantity = parseFloat(quantityInput.value) || 0;
    
    if (currentQuantity === 0) {
        // Set quantity to 1 when card is clicked and quantity is 0
        quantityInput.value = 1;
        updateInventoryItemSelection(itemId, 1);
    }
}

function updateInventoryQuantity(itemId, change) {
    const quantityInput = document.querySelector(`[data-item-id="${itemId}"] .inventory-quantity-input`);
    const currentQuantity = parseFloat(quantityInput.value) || 0;
    const maxStock = parseFloat(quantityInput.dataset.maxStock) || 0;
    
    let newQuantity = currentQuantity + change;
    
    // Ensure quantity is within bounds
    newQuantity = Math.max(0, Math.min(newQuantity, maxStock));
    
    quantityInput.value = newQuantity;
    
    // Update inventory item selection
    updateInventoryItemSelection(itemId, newQuantity);
}

function updateInventoryItemSelection(itemId, quantity) {
    const itemCard = document.querySelector(`[data-item-id="${itemId}"]`);
    const itemName = itemCard.querySelector('.service-name').textContent;
    const itemPriceText = itemCard.querySelector('.service-price').textContent;
    const itemPrice = parseFloat(itemPriceText.replace(/[^0-9.]/g, ''));
    
    // Check if item already exists to preserve custom price
    const existingItem = selectedInventoryItems.find(item => item.id === itemId);
    
    // Remove existing entry if any
    selectedInventoryItems = selectedInventoryItems.filter(item => item.id !== itemId);
    
    if (quantity > 0) {
        // Add or update inventory item
        itemCard.classList.add('selected');
        
        // Preserve custom price if it exists, otherwise use current display price
        const finalPrice = existingItem && existingItem.customPrice ? existingItem.customPrice : itemPrice;
        const customPrice = existingItem && existingItem.customPrice ? existingItem.customPrice : null;
        
        selectedInventoryItems.push({
            id: itemId,
            name: itemName,
            price: finalPrice,
            quantity: quantity,
            customPrice: customPrice  // This will be sent to backend if set
        });
    } else {
        // Remove inventory item
        itemCard.classList.remove('selected');
    }
    
    updateOrderSummary();
}

function onInventoryQuantityChange(input, itemId) {
    const quantity = parseFloat(input.value) || 0;
    const maxStock = parseFloat(input.dataset.maxStock) || 0;
    
    // Ensure quantity is within bounds
    if (quantity > maxStock) {
        input.value = maxStock;
        showToast(`Maximum available quantity is ${maxStock}`, 'warning');
    } else if (quantity < 0) {
        input.value = 0;
    }
    
    updateInventoryItemSelection(itemId, parseFloat(input.value));
}

// Customer Parts Functions
let customerPartIdCounter = 1; // For generating unique IDs for custom parts

function addCustomerPart() {
    const nameInput = document.getElementById('customerPartName');
    const quantityInput = document.getElementById('customerPartQuantity');
    
    const name = nameInput.value.trim();
    const quantity = parseFloat(quantityInput.value) || 1;
    
    if (!name) {
        showToast('Please enter a part name', 'warning');
        return;
    }
    
    if (quantity < 0.01) {
        showToast('Quantity must be at least 1', 'warning');
        return;
    }
    
    // Create customer part object
    const customerPart = {
        id: 'custom_' + customerPartIdCounter++,
        name: name,
        quantity: quantity,
        isCustom: true
    };
    
    // Add to selected customer parts
    selectedCustomerParts.push(customerPart);
    
    // Clear inputs
    nameInput.value = '';
    quantityInput.value = 1;
    
    // Update display
    updateCustomerPartsDisplay();
    updateOrderSummary();
    
    showToast('Customer part added successfully', 'success');
}

function updateCustomerPartsDisplay() {
    const display = document.getElementById('customerPartsListDisplay');
    
    if (selectedCustomerParts.length === 0) {
        display.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-gift"></i>
                <p>No customer parts added yet</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    selectedCustomerParts.forEach((part, index) => {
        html += `
            <div class="customer-part-item" data-part-id="${part.id}">
                <div class="customer-part-info">
                    <h6 class="customer-part-name">
                        <i class="fas fa-gift text-success"></i>
                        ${part.name}
                    </h6>
                    <p class="customer-part-quantity">Quantity: ${part.quantity}</p>
                </div>
                <div class="customer-part-actions">
                    <button type="button" class="btn-edit-part" onclick="editCustomerPart('${part.id}')">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button type="button" class="btn-remove-part" onclick="removeCustomerPart('${part.id}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    });
    
    display.innerHTML = html;
}

function editCustomerPart(partId) {
    const part = selectedCustomerParts.find(p => p.id === partId);
    if (!part) return;
    
    const newName = prompt('Edit part name:', part.name);
    if (newName === null) return; // User cancelled
    
    if (!newName.trim()) {
        showToast('Part name cannot be empty', 'warning');
        return;
    }
    
    const newQuantity = prompt('Edit quantity:', part.quantity);
    if (newQuantity === null) return; // User cancelled
    
    const quantity = parseInt(newQuantity);
    if (isNaN(quantity) || quantity < 1) {
        showToast('Quantity must be a number greater than 0', 'warning');
        return;
    }
    
    // Update the part
    part.name = newName.trim();
    part.quantity = quantity;
    
    // Update displays
    updateCustomerPartsDisplay();
    updateOrderSummary();
    
    showToast('Customer part updated successfully', 'success');
}

function removeCustomerPart(partId) {
    if (!confirm('Are you sure you want to remove this customer part?')) {
        return;
    }
    
    // Remove from selected customer parts
    selectedCustomerParts = selectedCustomerParts.filter(part => part.id !== partId);
    
    // Update displays
    updateCustomerPartsDisplay();
    updateOrderSummary();
    
    showToast('Customer part removed successfully', 'success');
}

// Price Editing Functions
let currentPriceEdit = null;

function editPrice(type, itemId, currentPrice, minimumPrice) {
    // Close any existing price edit
    if (currentPriceEdit) {
        cancelPriceEdit();
    }
    
    const priceDisplay = event.target;
    const controls = priceDisplay.nextElementSibling;
    const input = controls.querySelector('.price-edit-input');
    
    // Set current edit context
    currentPriceEdit = {
        type: type,
        itemId: itemId,
        element: priceDisplay,
        controls: controls,
        originalPrice: currentPrice,
        minimumPrice: minimumPrice
    };
    
    // Set input value and constraints
    input.value = currentPrice;
    input.min = minimumPrice;
    
    // Show controls
    controls.classList.add('active');
    input.focus();
    input.select();
}

function savePrice(type, itemId) {
    if (!currentPriceEdit || currentPriceEdit.itemId !== itemId) return;
    
    const input = currentPriceEdit.controls.querySelector('.price-edit-input');
    const newPrice = parseFloat(input.value);
    
    if (isNaN(newPrice) || newPrice < currentPriceEdit.minimumPrice) {
        showToast(`Price cannot be less than KES ${currentPriceEdit.minimumPrice}`, 'warning');
        return;
    }
    
    // Update the display
    currentPriceEdit.element.textContent = `KES ${newPrice.toFixed(2)}`;
    
    // Update the item's price in memory
    updateItemPrice(type, itemId, newPrice);
    
    // Debug logging
    console.log('Price updated for', type, itemId, 'to', newPrice);
    if (type === 'service') {
        console.log('Current selectedServices:', JSON.stringify(selectedServices, null, 2));
    }
    
    // Close the edit
    cancelPriceEdit();
    
    // Update order summary
    updateOrderSummary();
    
    showToast('Price updated successfully', 'success');
}

function cancelPriceEdit() {
    if (!currentPriceEdit) return;
    
    currentPriceEdit.controls.classList.remove('active');
    currentPriceEdit = null;
}

function updateItemPrice(type, itemId, newPrice) {
    if (type === 'service') {
        const service = selectedServices.find(s => s.id === itemId || s.id === itemId.toString());
        if (service) {
            service.price = newPrice;
            service.customPrice = newPrice;
            console.log('Updated existing service in selectedServices:', service);
        } else {
            // Service not in selectedServices yet, store the custom price for when it gets selected
            console.log('Service not found in selectedServices, storing custom price for later');
            // Store in a global object for later use
            if (!window.pendingCustomPrices) window.pendingCustomPrices = {};
            if (!window.pendingCustomPrices.services) window.pendingCustomPrices.services = {};
            window.pendingCustomPrices.services[itemId] = newPrice;
            console.log('Stored pending custom price:', window.pendingCustomPrices.services);
        }
    } else if (type === 'package') {
        if (selectedPackage && (selectedPackage.id === itemId || selectedPackage.id === itemId.toString())) {
            selectedPackage.price = newPrice;
            selectedPackage.customPrice = newPrice;
        }
    } else if (type === 'inventory') {
        const item = selectedInventoryItems.find(i => i.id === itemId || i.id === itemId.toString());
        if (item) {
            item.price = newPrice;
            item.customPrice = newPrice;
        } else {
            // Store pending custom price for inventory too
            if (!window.pendingCustomPrices) window.pendingCustomPrices = {};
            if (!window.pendingCustomPrices.inventory) window.pendingCustomPrices.inventory = {};
            window.pendingCustomPrices.inventory[itemId] = newPrice;
        }
    }
}

// Update the existing updateOrderSummary function to handle inventory items
function updateOrderSummary() {
    const selectedServicesDisplay = document.getElementById('selectedServicesDisplay');
    const selectedServicesList = document.getElementById('selectedServicesList');
    const summaryTotals = document.getElementById('summaryTotals');
    
    let hasSelection = false;
    let subtotal = 0;
    let totalDuration = 0;
    let servicesHtml = '';
    
    // Determine active type based on what's selected
    let activeType = null;
    if (selectedPackage) {
        activeType = 'package';
    } else if (selectedServices.length > 0 && (selectedInventoryItems.length > 0 || selectedCustomerParts.length > 0)) {
        activeType = 'mixed'; // Services and inventory/customer parts
    } else if (selectedServices.length > 0) {
        activeType = 'individual';
    } else if (selectedInventoryItems.length > 0 && selectedCustomerParts.length > 0) {
        activeType = 'mixed'; // Both inventory and customer parts
    } else if (selectedInventoryItems.length > 0) {
        activeType = 'inventory';
    } else if (selectedCustomerParts.length > 0) {
        activeType = 'customerParts';
    }
    
    if (activeType === 'package' && selectedPackage) {
        // Package selected
        hasSelection = true;
        subtotal = selectedPackage.price;
        totalDuration = selectedPackage.duration;
        
        servicesHtml = `
            <div class="selected-service-item">
                <div class="service-item-name">${selectedPackage.name} (Package)</div>
                <div class="service-item-price">KES ${selectedPackage.price.toFixed(2)}</div>
            </div>
        `;
    } else if (activeType === 'individual' || activeType === 'mixed') {
        // Individual services selected
        if (selectedServices.length > 0) {
            hasSelection = true;
            selectedServices.forEach(service => {
                subtotal += service.price;
                totalDuration += service.duration;
                servicesHtml += `
                    <div class="selected-service-item">
                        <div class="service-item-name">${service.name}</div>
                        <div class="service-item-price">KES ${service.price.toFixed(2)}</div>
                    </div>
                `;
            });
        }
        
        // Add inventory items if mixed
        if (activeType === 'mixed' || activeType === 'inventory') {
            selectedInventoryItems.forEach(item => {
                hasSelection = true;
                const itemTotal = item.price * item.quantity;
                subtotal += itemTotal;
                servicesHtml += `
                    <div class="selected-service-item">
                        <div class="service-item-name">${item.name} (x${item.quantity})</div>
                        <div class="service-item-price">KES ${itemTotal.toFixed(2)}</div>
                    </div>
                `;
            });
        }
        
        // Add customer-provided parts (always free)
        if (activeType === 'mixed' || activeType === 'customerParts') {
            selectedCustomerParts.forEach(item => {
                hasSelection = true;
                // Customer parts don't add to subtotal (they're free)
                servicesHtml += `
                    <div class="selected-service-item customer-part-item">
                        <div class="service-item-name">
                            <i class="fas fa-gift text-success me-1"></i>
                            ${item.name} (x${item.quantity}) - Customer Part
                        </div>
                        <div class="service-item-price text-success">FREE</div>
                    </div>
                `;
            });
        }
    } else if (activeType === 'inventory') {
        // Only inventory items selected
        selectedInventoryItems.forEach(item => {
            hasSelection = true;
            const itemTotal = item.price * item.quantity;
            subtotal += itemTotal;
            servicesHtml += `
                <div class="selected-service-item">
                    <div class="service-item-name">${item.name} (x${item.quantity})</div>
                    <div class="service-item-price">KES ${itemTotal.toFixed(2)}</div>
                </div>
            `;
        });
    } else if (activeType === 'customerParts') {
        // Only customer-provided parts selected
        selectedCustomerParts.forEach(item => {
            hasSelection = true;
            // Customer parts don't add to subtotal (they're free)
            servicesHtml += `
                <div class="selected-service-item customer-part-item">
                    <div class="service-item-name">
                        <i class="fas fa-gift text-success me-1"></i>
                        ${item.name} (x${item.quantity}) - Customer Part
                    </div>
                    <div class="service-item-price text-success">FREE</div>
                </div>
            `;
        });
    }
    
    if (hasSelection) {
        selectedServicesDisplay.style.display = 'none';
        selectedServicesList.style.display = 'block';
        selectedServicesList.innerHTML = servicesHtml;
        
        summaryTotals.style.display = 'block';
        
        // Assume prices are VAT inclusive - calculate breakdown
        const totalVatInclusive = subtotal; // Subtotal already includes VAT
        const taxAmount = totalVatInclusive / 1.16 * 0.16; // Extract VAT amount
        const subtotalExVat = totalVatInclusive - taxAmount; // Ex-VAT amount
        
        document.getElementById('subtotalAmount').textContent = `KES ${subtotalExVat.toFixed(2)}`;
        document.getElementById('taxAmount').textContent = `KES ${taxAmount.toFixed(2)}`;
        document.getElementById('totalAmount').textContent = `KES ${totalVatInclusive.toFixed(2)}`;
        document.getElementById('estimatedDuration').textContent = totalDuration;
    } else {
        selectedServicesDisplay.style.display = 'block';
        selectedServicesList.style.display = 'none';
        summaryTotals.style.display = 'none';
    }
    
    // Update mobile summary
    updateMobileSummary();
    
    // Update selected services data for form submission
    const selectedServicesData = document.getElementById('selectedServicesData');
    if (selectedServicesData) {
        let dataToSubmit = {};
        
        // Determine the correct type and structure
        if (selectedPackage) {
            dataToSubmit = {
                type: 'package',
                package_id: selectedPackage.id,
                custom_price: selectedPackage.customPrice || null
            };
        } else if (selectedServices.length > 0 && (selectedInventoryItems.length > 0 || selectedCustomerParts.length > 0)) {
            dataToSubmit = {
                type: 'mixed',
                service_ids: selectedServices.map(s => s.id),
                services_custom_prices: selectedServices.reduce((acc, s) => {
                    console.log('Processing service for custom prices (mixed):', s.id, 'customPrice:', s.customPrice);
                    if (s.customPrice) acc[s.id] = s.customPrice;
                    return acc;
                }, {}),
                inventory_items: selectedInventoryItems.map(item => ({
                    id: item.id,
                    quantity: item.quantity,
                    custom_price: item.customPrice || null
                })),
                customer_parts: selectedCustomerParts.map(part => ({
                    id: part.id,
                    name: part.name,
                    quantity: part.quantity,
                    is_custom: part.isCustom || false
                }))
            };
        } else if (selectedServices.length > 0) {
            dataToSubmit = {
                type: 'individual',
                service_ids: selectedServices.map(s => s.id),
                services_custom_prices: selectedServices.reduce((acc, s) => {
                    console.log('Processing service for custom prices:', s.id, 'customPrice:', s.customPrice);
                    if (s.customPrice) acc[s.id] = s.customPrice;
                    return acc;
                }, {})
            };
            console.log('Individual services dataToSubmit:', JSON.stringify(dataToSubmit, null, 2));
        } else if (selectedInventoryItems.length > 0 || selectedCustomerParts.length > 0) {
            dataToSubmit = {
                type: selectedInventoryItems.length > 0 ? 'inventory' : 'customerParts',
                inventory_items: selectedInventoryItems.map(item => ({
                    id: item.id,
                    quantity: item.quantity,
                    custom_price: item.customPrice || null
                })),
                customer_parts: selectedCustomerParts.map(part => ({
                    id: part.id,
                    name: part.name,
                    quantity: part.quantity,
                    is_custom: part.isCustom || false
                }))
            };
        } else {
            dataToSubmit = { type: null };
        }
        
        selectedServicesData.value = JSON.stringify(dataToSubmit);
        console.log('Updated selectedServicesData in updateOrderSummary:', dataToSubmit);
        console.log('selectedServices:', selectedServices);
        console.log('selectedPackage:', selectedPackage);  
        console.log('selectedInventoryItems:', selectedInventoryItems);
    }
}

// Package selected function
function updateOrderSummaryDisplay() {
    let hasSelection = false;
    let subtotal = 0;
    let totalDuration = 0;
    let servicesHtml = '';
    let activeType = 'individual';
    
    // Determine active type
    if (selectedPackage) {
        activeType = 'package';
    } else if (selectedServices.length > 0 && selectedInventoryItems.length > 0) {
        activeType = 'mixed';
    } else if (selectedServices.length > 0) {
        activeType = 'services';
    } else if (selectedInventoryItems.length > 0) {
        activeType = 'inventory';
    }
    
    // Package selected
    if (selectedPackage) {
        hasSelection = true;
        subtotal = selectedPackage.price;
        totalDuration = selectedPackage.duration;
        
        servicesHtml = `
            <div class="selected-service-item">
                <div class="service-item-name">
                    <strong>${selectedPackage.name}</strong>
                    <br><small>${selectedPackage.servicesCount} services included</small>
                </div>
                <div class="service-item-price">KES ${selectedPackage.price.toFixed(2)}</div>
            </div>
        `;
    }
    
    // Individual services selected
    if (selectedServices.length > 0) {
        hasSelection = true;
        
        selectedServices.forEach(service => {
            servicesHtml += `
                <div class="selected-service-item">
                    <div class="service-item-name">${service.name}</div>
                    <div class="service-item-price">KES ${service.price.toFixed(2)}</div>
                </div>
            `;
            subtotal += service.price;
            totalDuration += service.duration;
        });
    }
    
    // Inventory items selected
    if (selectedInventoryItems.length > 0) {
        hasSelection = true;
        
        selectedInventoryItems.forEach(item => {
            const itemTotal = item.price * item.quantity;
            servicesHtml += `
                <div class="selected-service-item">
                    <div class="service-item-name">
                        ${item.name}
                        <br><small>Qty: ${item.quantity} × KES ${item.price.toFixed(2)}</small>
                    </div>
                    <div class="service-item-price">KES ${itemTotal.toFixed(2)}</div>
                </div>
            `;
            subtotal += itemTotal;
        });
    }
    
    if (!hasSelection) {
        selectedServicesDisplay.style.display = 'block';
        selectedServicesList.style.display = 'none';
        summaryTotals.style.display = 'none';
        return;
    }
    
    selectedServicesDisplay.style.display = 'none';
    selectedServicesList.style.display = 'block';
    summaryTotals.style.display = 'block';
    
    selectedServicesList.innerHTML = servicesHtml;
    
    // Update totals with inclusive VAT
    const totalInclusiveVAT = subtotal;
    const taxAmount = totalInclusiveVAT / 1.16 * 0.16; // Extract VAT amount  
    const subtotalExVAT = totalInclusiveVAT - taxAmount; // Ex-VAT amount
    
    document.getElementById('subtotalAmount').textContent = `KES ${subtotalExVAT.toFixed(2)}`;
    document.getElementById('taxAmount').textContent = `KES ${taxAmount.toFixed(2)}`;
    document.getElementById('totalAmount').textContent = `KES ${totalInclusiveVAT.toFixed(2)}`;
    document.getElementById('estimatedDuration').textContent = totalDuration;
    
    // Update hidden field based on what's selected
    if (selectedPackage) {
        document.getElementById('selectedServicesData').value = JSON.stringify({
            type: 'package',
            package_id: selectedPackage.id
        });
    } else if (selectedServices.length > 0 && selectedInventoryItems.length > 0) {
        // Mixed selection
        document.getElementById('selectedServicesData').value = JSON.stringify({
            type: 'mixed',
            service_ids: selectedServices.map(s => s.id),
            inventory_items: selectedInventoryItems.map(item => ({
                id: item.id,
                quantity: item.quantity
            }))
        });
    } else if (selectedInventoryItems.length > 0) {
        document.getElementById('selectedServicesData').value = JSON.stringify({
            type: 'inventory',
            inventory_items: selectedInventoryItems.map(item => ({
                id: item.id,
                quantity: item.quantity
            }))
        });
    } else {
        document.getElementById('selectedServicesData').value = JSON.stringify({
            type: 'individual',
            service_ids: selectedServices.map(s => s.id)
        });
    }
}

// Update the existing validateServicesStep function to handle inventory
function validateServicesStep() {
    // Check if any selection exists
    const hasPackage = selectedPackage !== null;
    const hasServices = selectedServices.length > 0;
    const hasInventoryItems = selectedInventoryItems.length > 0;
    const hasCustomerParts = selectedCustomerParts.length > 0;
    
    if (!hasPackage && !hasServices && !hasInventoryItems && !hasCustomerParts) {
        showToast('Please select at least one service, package, inventory item, or customer part', 'error');
        return false;
    }
    
    return true;
}
