// POS System JavaScript
class PosSystem {
    constructor() {
        this.config = {};
        this.selectedCustomer = null;
        this.selectedVehicle = null;
        this.cart = [];
        this.currentCategory = 'all';
        this.paymentMethod = 'cash';
        this.customerSearchTimeout = null;
        
        // Cache DOM elements
        this.elements = {};
    }
    
    static init(config = {}) {
        console.log('POS: Starting initialization with config:', config);
        const instance = new PosSystem();
        instance.config = config;
        instance.initializeElements();
        instance.bindEvents();
        instance.loadInitialData();
        window.posSystem = instance;
        console.log('POS: Initialization complete');
        
        // Hide loading overlay
        TabletBase.hideLoading();
        
        return instance;
    }
    
    initializeElements() {
        console.log('POS: Initializing elements...');
        this.elements = {
            customerSearch: document.getElementById('customerSearch'),
            customerSearchResults: document.getElementById('customerSearchResults'),
            selectedCustomer: document.getElementById('selectedCustomer'),
            customerName: document.getElementById('customerName'),
            customerPhone: document.getElementById('customerPhone'),
            vehicleSelection: document.getElementById('vehicleSelection'),
            vehicleSelect: document.getElementById('vehicleSelect'),
            servicesGrid: document.getElementById('servicesGrid'),
            inventoryGrid: document.getElementById('inventoryGrid'),
            orderItems: document.getElementById('orderItems'),
            orderTotals: document.getElementById('orderTotals'),
            paymentSection: document.getElementById('paymentSection'),
            commissionSection: document.getElementById('commissionSection'),
            subtotal: document.getElementById('subtotal'),
            tax: document.getElementById('tax'),
            total: document.getElementById('total'),
            totalCommission: document.getElementById('totalCommission'),
            amountReceived: document.getElementById('amountReceived'),
            changeDisplay: document.getElementById('changeDisplay'),
            changeAmount: document.getElementById('changeAmount'),
            processPaymentBtn: document.getElementById('processPaymentBtn'),
            queueItems: document.getElementById('queueItems')
        };
        
        // Check for missing elements
        Object.keys(this.elements).forEach(key => {
            if (!this.elements[key]) {
                console.warn(`POS: Missing element: ${key}`);
            }
        });
        console.log('POS: Elements initialized');
    }
    
    bindEvents() {
        // Customer search
        if (this.elements.customerSearch) {
            this.elements.customerSearch.addEventListener('input', (e) => {
                clearTimeout(this.customerSearchTimeout);
                this.customerSearchTimeout = setTimeout(() => {
                    this.searchCustomers(e.target.value);
                }, 300);
            });
        }
        
        // Category tabs
        document.querySelectorAll('.category-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchCategory(e.target.dataset.category);
            });
        });
        
        // Service/inventory cards
        this.bindProductCards();
        
        // Payment methods
        document.querySelectorAll('.payment-method').forEach(method => {
            method.addEventListener('click', (e) => {
                this.selectPaymentMethod(e.target.dataset.method);
            });
        });
        
        // Amount received input
        if (this.elements.amountReceived) {
            this.elements.amountReceived.addEventListener('input', () => {
                this.calculateChange();
            });
        }
        
        // Customer form
        const customerForm = document.getElementById('customerForm');
        if (customerForm) {
            customerForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.createCustomer(new FormData(customerForm));
            });
        }
        
        // Add vehicle form
        const addVehicleForm = document.getElementById('addVehicleForm');
        if (addVehicleForm) {
            addVehicleForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.addVehicleToCustomer(new FormData(addVehicleForm));
            });
        }
        
        // Vehicle selection
        if (this.elements.vehicleSelect) {
            this.elements.vehicleSelect.addEventListener('change', (e) => {
                this.selectVehicle(e.target.value);
            });
        }
    }
    
    bindProductCards() {
        // Service cards
        document.querySelectorAll('.service-card').forEach(card => {
            card.addEventListener('click', () => {
                this.addServiceToCart(card.dataset.serviceId);
            });
        });
        
        // Inventory cards  
        document.querySelectorAll('.inventory-card').forEach(card => {
            card.addEventListener('click', () => {
                this.addInventoryToCart(card.dataset.itemId);
            });
        });
    }
    
    async loadInitialData() {
        console.log('POS: Loading initial data...');
        try {
            // Initialize services grid as active by default
            if (this.elements.servicesGrid) {
                this.elements.servicesGrid.classList.add('active');
            }
            
            // Set default category tab as active
            const defaultTab = document.querySelector('.category-tab[data-category="all"]');
            if (defaultTab) {
                defaultTab.classList.add('active');
            }
            
            // Load any initial data needed
            await this.refreshQueue();
            await this.loadAvailableWorkers();
            console.log('POS: Initial data loaded successfully');
        } catch (error) {
            console.error('POS: Error loading initial data:', error);
        }
    }
    
    async loadAvailableWorkers() {
        try {
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/businesses/ajax/available-workers/`
            );
            
            if (response.success) {
                const workerSelect = document.getElementById('assignedWorker');
                if (workerSelect) {
                    // Clear existing options except the first one
                    const firstOption = workerSelect.firstElementChild;
                    workerSelect.innerHTML = '';
                    workerSelect.appendChild(firstOption);
                    
                    // Add available workers
                    response.workers.forEach(worker => {
                        const option = document.createElement('option');
                        option.value = worker.id;
                        option.textContent = `${worker.name} (${worker.status})`;
                        workerSelect.appendChild(option);
                    });
                }
            }
        } catch (error) {
            console.error('Error loading workers:', error);
        }
    }
    
    // Customer Management
    async searchCustomers(query) {
        if (!query.trim()) {
            this.elements.customerSearchResults.style.display = 'none';
            return;
        }
        
        try {
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/services/ajax/customer/search/?q=${encodeURIComponent(query)}`
            );
            
            this.displayCustomerResults(response.customers || []);
        } catch (error) {
            console.error('Error searching customers:', error);
            TabletBase.showToast('Error searching customers', 'error');
        }
    }
    
    displayCustomerResults(customers) {
        const results = this.elements.customerSearchResults;
        
        if (customers.length === 0) {
            results.innerHTML = '<div class="search-result-item">No customers found</div>';
        } else {
            results.innerHTML = customers.map(customer => `
                <div class="search-result-item" onclick="posSystem.selectCustomer('${customer.id}')">
                    <strong>${customer.full_name}</strong><br>
                    <small>${customer.phone}</small>
                </div>
            `).join('');
        }
        
        results.style.display = 'block';
    }
    
    async selectCustomer(customerId) {
        try {
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/services/ajax/customer/${customerId}/details/`
            );
            
            this.selectedCustomer = response.customer;
            this.displaySelectedCustomer();
            this.loadCustomerVehicles();
            this.hideCustomerSearch();
            
        } catch (error) {
            console.error('Error loading customer:', error);
            TabletBase.showToast('Error loading customer details', 'error');
        }
    }
    
    displaySelectedCustomer() {
        if (!this.selectedCustomer) return;
        
        this.elements.customerName.textContent = this.selectedCustomer.full_name;
        this.elements.customerPhone.textContent = this.selectedCustomer.phone;
        this.elements.selectedCustomer.classList.add('active');
    }
    
    async loadCustomerVehicles() {
        if (!this.selectedCustomer) return;
        
        try {
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/services/ajax/customer/${this.selectedCustomer.id}/vehicles/`
            );
            
            this.populateVehicleSelect(response.vehicles || []);
        } catch (error) {
            console.error('Error loading vehicles:', error);
        }
    }
    
    populateVehicleSelect(vehicles) {
        const select = this.elements.vehicleSelect;
        const addVehicleBtn = document.getElementById('addVehicleBtn');
        
        select.innerHTML = '<option value="">Choose vehicle...</option>';
        
        if (vehicles.length === 0) {
            // Show add vehicle button if customer has no vehicles
            addVehicleBtn.classList.add('show');
            select.innerHTML += '<option value="" disabled>No vehicles found - Add one below</option>';
        } else {
            addVehicleBtn.classList.remove('show');
            vehicles.forEach(vehicle => {
                const option = document.createElement('option');
                option.value = vehicle.id;
                option.textContent = `${vehicle.registration_number} - ${vehicle.make} ${vehicle.model}`;
                select.appendChild(option);
            });
        }
    }
    
    selectVehicle(vehicleId) {
        if (!vehicleId) {
            this.selectedVehicle = null;
            return;
        }
        
        // Find vehicle in the current options
        const option = this.elements.vehicleSelect.querySelector(`option[value="${vehicleId}"]`);
        if (option) {
            this.selectedVehicle = {
                id: vehicleId,
                display: option.textContent
            };
        }
    }
    
    clearCustomer() {
        this.selectedCustomer = null;
        this.selectedVehicle = null;
        this.elements.selectedCustomer.classList.remove('active');
        this.elements.customerSearch.value = '';
        
        // Hide add vehicle button
        const addVehicleBtn = document.getElementById('addVehicleBtn');
        if (addVehicleBtn) {
            addVehicleBtn.classList.remove('show');
        }
        
        this.hideCustomerSearch();
    }
    
    hideCustomerSearch() {
        this.elements.customerSearchResults.style.display = 'none';
    }
    
    // Category Management
    switchCategory(category) {
        this.currentCategory = category;
        
        // Update active tab
        document.querySelectorAll('.category-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.category === category);
        });
        
        // Show/hide appropriate grids
        if (category === 'inventory') {
            this.elements.servicesGrid.classList.remove('active');
            this.elements.inventoryGrid.classList.add('active');
        } else {
            this.elements.servicesGrid.classList.add('active');
            this.elements.inventoryGrid.classList.remove('active');
            
            // Filter services by category
            this.filterServices(category);
        }
    }
    
    filterServices(category) {
        const serviceCards = document.querySelectorAll('.service-card');
        
        serviceCards.forEach(card => {
            if (category === 'all' || card.dataset.category === category) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    }
    
    // Cart Management
    async addServiceToCart(serviceId) {
        if (!this.validateCustomerSelection()) return;
        
        try {
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/services/ajax/service/${serviceId}/data/`
            );
            
            // The response IS the service data
            const service = response;
            const existingItem = this.cart.find(item => 
                item.type === 'service' && item.id === serviceId
            );
            
            if (existingItem) {
                existingItem.quantity += 1;
            } else {
                this.cart.push({
                    type: 'service',
                    id: serviceId,
                    name: service.name,
                    price: parseFloat(service.base_price),
                    commission_rate: parseFloat(service.commission_rate || 0),
                    commission_type: service.commission_type || 'percentage',
                    fixed_commission: parseFloat(service.fixed_commission || 0),
                    quantity: 1,
                    duration: service.estimated_duration
                });
            }
            
            this.updateCartDisplay();
            TabletBase.showToast(`${service.name} added to order`, 'success');
            
        } catch (error) {
            console.error('Error adding service:', error);
            TabletBase.showToast('Error adding service to order', 'error');
        }
    }
    
    async addInventoryToCart(itemId) {
        if (!this.validateCustomerSelection()) return;
        
        try {
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/inventory/ajax/item/${itemId}/`
            );
            
            const item = response.item;
            
            if (item.current_stock <= 0) {
                TabletBase.showToast('Item is out of stock', 'warning');
                return;
            }
            
            const existingItem = this.cart.find(cartItem => 
                cartItem.type === 'inventory' && cartItem.id === itemId
            );
            
            if (existingItem) {
                if (existingItem.quantity >= item.current_stock) {
                    TabletBase.showToast('Insufficient stock', 'warning');
                    return;
                }
                existingItem.quantity += 1;
            } else {
                this.cart.push({
                    type: 'inventory',
                    id: itemId,
                    name: item.name,
                    price: parseFloat(item.selling_price),
                    quantity: 1,
                    stock_available: item.current_stock,
                    unit: item.unit
                });
            }
            
            this.updateCartDisplay();
            TabletBase.showToast(`${item.name} added to order`, 'success');
            
        } catch (error) {
            console.error('Error adding inventory:', error);
            TabletBase.showToast('Error adding item to order', 'error');
        }
    }
    
    validateCustomerSelection() {
        if (!this.selectedCustomer) {
            TabletBase.showToast('Please select a customer first', 'warning');
            return false;
        }
        
        if (!this.selectedVehicle) {
            TabletBase.showToast('Please select a vehicle first', 'warning');
            return false;
        }
        
        return true;
    }
    
    updateCartDisplay() {
        if (this.cart.length === 0) {
            this.elements.orderItems.innerHTML = `
                <div class="empty-cart">
                    <i class="fas fa-shopping-cart"></i>
                    <p>No items selected</p>
                </div>
            `;
            this.elements.orderTotals.classList.remove('active');
            this.elements.paymentSection.classList.remove('active');
            this.elements.commissionSection.classList.remove('active');
            return;
        }
        
        // Display cart items
        this.elements.orderItems.innerHTML = this.cart.map((item, index) => `
            <div class="order-item">
                <div class="item-details">
                    <h5>${item.name}</h5>
                    <p>KES ${item.price.toFixed(2)} each</p>
                </div>
                <div class="item-controls">
                    <button class="quantity-btn" onclick="posSystem.decreaseQuantity(${index})">
                        <i class="fas fa-minus"></i>
                    </button>
                    <span class="quantity">${item.quantity}</span>
                    <button class="quantity-btn" onclick="posSystem.increaseQuantity(${index})">
                        <i class="fas fa-plus"></i>
                    </button>
                </div>
                <div class="item-total">
                    KES ${(item.price * item.quantity).toFixed(2)}
                </div>
            </div>
        `).join('');
        
        // Calculate and display totals
        this.calculateTotals();
        this.elements.orderTotals.classList.add('active');
        this.elements.paymentSection.classList.add('active');
        this.elements.commissionSection.classList.add('active');
    }
    
    calculateTotals() {
        const subtotal = this.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        const tax = subtotal * 0.16; // 16% VAT
        const total = subtotal + tax;
        
        // Calculate commission
        let totalCommission = 0;
        this.cart.forEach(item => {
            if (item.type === 'service' && item.commission_rate > 0) {
                if (item.commission_type === 'percentage') {
                    totalCommission += (item.price * item.quantity) * (item.commission_rate / 100);
                } else if (item.commission_type === 'fixed') {
                    totalCommission += item.fixed_commission * item.quantity;
                }
            }
        });
        
        // Update display
        this.elements.subtotal.textContent = `KES ${subtotal.toFixed(2)}`;
        this.elements.tax.textContent = `KES ${tax.toFixed(2)}`;
        this.elements.total.textContent = `KES ${total.toFixed(2)}`;
        this.elements.totalCommission.textContent = `KES ${totalCommission.toFixed(2)}`;
        
        // Update amount received placeholder
        this.elements.amountReceived.placeholder = `Total: KES ${total.toFixed(2)}`;
    }
    
    increaseQuantity(index) {
        const item = this.cart[index];
        
        // Check stock for inventory items
        if (item.type === 'inventory' && item.quantity >= item.stock_available) {
            TabletBase.showToast('Insufficient stock', 'warning');
            return;
        }
        
        item.quantity += 1;
        this.updateCartDisplay();
    }
    
    decreaseQuantity(index) {
        const item = this.cart[index];
        
        if (item.quantity > 1) {
            item.quantity -= 1;
            this.updateCartDisplay();
        } else {
            this.removeFromCart(index);
        }
    }
    
    removeFromCart(index) {
        this.cart.splice(index, 1);
        this.updateCartDisplay();
    }
    
    clearCart() {
        this.cart = [];
        this.updateCartDisplay();
        TabletBase.showToast('Cart cleared', 'info');
    }
    
    // Payment Management
    selectPaymentMethod(method) {
        this.paymentMethod = method;
        
        document.querySelectorAll('.payment-method').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.method === method);
        });
        
        // Show/hide pay later option
        const payLaterOption = document.getElementById('payLaterOption');
        if (payLaterOption) {
            payLaterOption.style.display = (method !== 'cash') ? 'block' : 'none';
        }
    }
    
    calculateChange() {
        const amountReceived = parseFloat(this.elements.amountReceived.value) || 0;
        const total = this.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0) * 1.16; // Include tax
        
        const change = amountReceived - total;
        
        if (this.paymentMethod === 'cash') {
            if (change >= 0) {
                this.elements.changeAmount.textContent = `KES ${change.toFixed(2)}`;
                this.elements.changeDisplay.classList.add('active');
                this.elements.processPaymentBtn.disabled = false;
            } else {
                this.elements.changeDisplay.classList.remove('active');
                this.elements.processPaymentBtn.disabled = true;
            }
        } else {
            // For non-cash payments, disable change calculation
            this.elements.changeDisplay.classList.remove('active');
            this.elements.processPaymentBtn.disabled = false;
        }
    }
    
    async processPayment() {
        if (this.cart.length === 0) {
            TabletBase.showToast('Cart is empty', 'warning');
            return;
        }
        
        if (!this.validateCustomerSelection()) return;
        
        const processPaymentNow = !document.getElementById('payLater')?.checked;
        const assignedWorkerId = document.getElementById('assignedWorker')?.value || null;
        
        let amountReceived = 0;
        if (processPaymentNow) {
            amountReceived = parseFloat(this.elements.amountReceived.value) || 0;
            const total = this.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0) * 1.16;
            
            if (this.paymentMethod === 'cash' && amountReceived < total) {
                TabletBase.showToast('Insufficient amount received', 'warning');
                return;
            }
        }
        
        TabletBase.showLoading(processPaymentNow ? 'Processing payment...' : 'Creating order...');
        
        try {
            const orderData = {
                customer_id: this.selectedCustomer.id,
                vehicle_id: this.selectedVehicle.id,
                payment_method: this.paymentMethod,
                amount_received: amountReceived,
                process_payment_now: processPaymentNow,
                assigned_worker_id: assignedWorkerId,
                items: this.cart.map(item => ({
                    type: item.type,
                    id: item.id,
                    quantity: item.quantity,
                    price: item.price
                }))
            };
            
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/services/ajax/create-pos-order/`, 
                {
                    method: 'POST',
                    body: JSON.stringify(orderData)
                }
            );
            
            if (response.success) {
                const message = processPaymentNow ? 
                    'Payment processed successfully!' : 
                    'Order created successfully! Payment can be processed later.';
                    
                TabletBase.showToast(message, 'success');
                this.resetOrderForm();
                await this.refreshQueue();
                
                // Show commission info if applicable
                if (response.commission > 0) {
                    TabletBase.showToast(
                        `Commission earned: KES ${response.commission.toFixed(2)}`, 
                        'info'
                    );
                }
            } else {
                TabletBase.showToast(response.message || 'Order processing failed', 'error');
            }
            
        } catch (error) {
            console.error('Error processing order:', error);
            TabletBase.showToast('Error processing order', 'error');
        } finally {
            TabletBase.hideLoading();
        }
    }
    
    resetOrderForm() {
        this.cart = [];
        this.selectedCustomer = null;
        this.selectedVehicle = null;
        this.elements.customerSearch.value = '';
        this.elements.selectedCustomer.classList.remove('active');
        this.elements.amountReceived.value = '';
        this.updateCartDisplay();
    }
    
    // Process payment for existing unpaid order
    async processExistingOrderPayment(orderId, paymentMethod = 'cash') {
        const modal = document.getElementById('paymentModal');
        if (!modal) {
            console.error('Payment modal not found');
            return;
        }
        
        // Get payment details from modal
        const amountReceived = parseFloat(document.getElementById('modalAmountReceived')?.value || 0);
        const selectedPaymentMethod = document.querySelector('input[name="modalPaymentMethod"]:checked')?.value || paymentMethod;
        
        if (amountReceived <= 0) {
            TabletBase.showToast('Please enter amount received', 'warning');
            return;
        }
        
        TabletBase.showLoading('Processing payment...');
        
        try {
            const formData = new FormData();
            formData.append('order_id', orderId);
            formData.append('payment_method', selectedPaymentMethod);
            formData.append('amount_received', amountReceived);
            formData.append('csrfmiddlewaretoken', this.config.csrf_token);
            
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/services/ajax/process-pos-payment/`, 
                {
                    method: 'POST',
                    body: formData
                }
            );
            
            if (response.success) {
                TabletBase.showToast('Payment processed successfully!', 'success');
                
                // Update UI
                const orderCard = document.querySelector(`[data-order-id="${orderId}"]`);
                if (orderCard) {
                    if (response.payment_status === 'paid') {
                        orderCard.querySelector('.payment-status')?.classList.replace('badge-warning', 'badge-success');
                        orderCard.querySelector('.payment-status')?.textContent = 'Paid';
                        
                        // Show payment details
                        if (response.change_amount > 0) {
                            TabletBase.showToast(`Change: KES ${response.change_amount.toFixed(2)}`, 'info');
                        }
                    } else {
                        orderCard.querySelector('.payment-status')?.textContent = `Partial (Balance: KES ${response.balance.toFixed(2)})`;
                    }
                }
                
                // Close modal
                bootstrap.Modal.getInstance(modal)?.hide();
                
                // Refresh queue and dashboard
                await this.refreshQueue();
                await this.loadDashboardMetrics();
                
            } else {
                TabletBase.showToast(response.message || 'Payment processing failed', 'error');
            }
            
        } catch (error) {
            console.error('Error processing payment:', error);
            TabletBase.showToast('Error processing payment', 'error');
        } finally {
            TabletBase.hideLoading();
        }
    }
    
    // Complete order (move to active queue)
    async completeOrder(orderId) {
        if (!confirm('Complete this order and add to service queue?')) {
            return;
        }
        
        TabletBase.showLoading('Completing order...');
        
        try {
            const formData = new FormData();
            formData.append('order_id', orderId);
            formData.append('csrfmiddlewaretoken', this.config.csrf_token);
            
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/services/ajax/complete-pos-order/`, 
                {
                    method: 'POST',
                    body: formData
                }
            );
            
            if (response.success) {
                TabletBase.showToast('Order completed and added to service queue!', 'success');
                
                // Update UI
                const orderCard = document.querySelector(`[data-order-id="${orderId}"]`);
                if (orderCard) {
                    orderCard.remove();
                }
                
                // Refresh queue
                await this.refreshQueue();
                
            } else {
                TabletBase.showToast(response.message || 'Order completion failed', 'error');
            }
            
        } catch (error) {
            console.error('Error completing order:', error);
            TabletBase.showToast('Error completing order', 'error');
        } finally {
            TabletBase.hideLoading();
        }
    }
    
    // Show payment modal for unpaid order
    showPaymentModal(orderId, orderTotal, customerName) {
        const modal = document.getElementById('paymentModal');
        if (!modal) {
            console.error('Payment modal not found');
            return;
        }
        
        // Update modal content
        document.getElementById('paymentOrderId').textContent = orderId;
        document.getElementById('paymentCustomerName').textContent = customerName;
        document.getElementById('paymentOrderTotal').textContent = `KES ${orderTotal.toFixed(2)}`;
        document.getElementById('modalAmountReceived').value = orderTotal.toFixed(2);
        
        // Show modal
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }
    
    // Customer Modal
    showCustomerModal() {
        const modal = new bootstrap.Modal(document.getElementById('customerModal'));
        modal.show();
    }
    
    showAddVehicleModal() {
        if (!this.selectedCustomer) {
            TabletBase.showToast('Please select a customer first', 'warning');
            return;
        }
        const modal = new bootstrap.Modal(document.getElementById('addVehicleModal'));
        modal.show();
    }

    async createCustomer(formData) {
        TabletBase.showLoading('Creating customer...');
        
        try {
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/services/ajax/create-customer/`,
                {
                    method: 'POST',
                    body: formData
                }
            );
            
            if (response.success) {
                TabletBase.showToast('Customer created successfully!', 'success');
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('customerModal'));
                modal.hide();
                
                // Select the new customer
                await this.selectCustomer(response.customer.id);
                
                // Reset form
                document.getElementById('customerForm').reset();
                
            } else {
                TabletBase.showToast(response.message || 'Failed to create customer', 'error');
            }
            
        } catch (error) {
            console.error('Error creating customer:', error);
            TabletBase.showToast('Error creating customer', 'error');
        } finally {
            TabletBase.hideLoading();
        }
    }
    
    async addVehicleToCustomer(formData) {
        if (!this.selectedCustomer) {
            TabletBase.showToast('No customer selected', 'error');
            return;
        }
        
        TabletBase.showLoading('Adding vehicle...');
        
        try {
            // Add customer_id to form data
            formData.append('customer_id', this.selectedCustomer.id);
            
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/services/ajax/add-vehicle/`,
                {
                    method: 'POST',
                    body: formData
                }
            );
            
            if (response.success) {
                TabletBase.showToast('Vehicle added successfully!', 'success');
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('addVehicleModal'));
                modal.hide();
                
                // Reload customer vehicles
                await this.loadCustomerVehicles();
                
                // Auto-select the new vehicle
                if (response.vehicle && response.vehicle.id) {
                    this.elements.vehicleSelect.value = response.vehicle.id;
                    this.selectVehicle(response.vehicle.id);
                }
                
                // Reset form
                document.getElementById('addVehicleForm').reset();
                
            } else {
                TabletBase.showToast(response.message || 'Failed to add vehicle', 'error');
            }
            
        } catch (error) {
            console.error('Error adding vehicle:', error);
            TabletBase.showToast('Error adding vehicle', 'error');
        } finally {
            TabletBase.hideLoading();
        }
    }    // Queue Management
    async refreshQueue() {
        try {
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/services/ajax/queue/status/`
            );
            
            if (response.queue) {
                this.displayQueue(response.queue);
            }
            
        } catch (error) {
            console.error('Error refreshing queue:', error);
        }
    }
    
    displayQueue(entries) {
        if (entries.length === 0) {
            this.elements.queueItems.innerHTML = `
                <div class="empty-queue">
                    <i class="fas fa-clipboard-list"></i>
                    <p>No items in queue</p>
                </div>
            `;
            return;
        }
        
        this.elements.queueItems.innerHTML = entries.map(entry => `
            <div class="queue-item" data-queue-id="${entry.id}">
                <div class="queue-number">${entry.queue_number}</div>
                <div class="queue-info">
                    <h5>${entry.order.order_number}</h5>
                    <p>${entry.order.customer.full_name} - ${entry.order.vehicle.registration_number}</p>
                    <div class="queue-services">
                        ${entry.order.order_items.map(item => 
                            `<span class="service-tag">${item.service.name}</span>`
                        ).join('')}
                    </div>
                </div>
                <div class="queue-status">
                    <span class="badge badge-${entry.status}">${entry.status_display}</span>
                    <div class="queue-actions">
                        ${this.getQueueActions(entry)}
                    </div>
                </div>
            </div>
        `).join('');
    }
    
    getQueueActions(entry) {
        if (entry.status === 'waiting' && entry.order.assigned_attendant_id == this.config.employee_id) {
            return `<button class="btn btn-sm btn-success" onclick="posSystem.startService('${entry.order.id}')">
                        <i class="fas fa-play"></i> Start
                    </button>`;
        } else if (entry.status === 'in_service' && entry.order.assigned_attendant_id == this.config.employee_id) {
            return `<button class="btn btn-sm btn-primary" onclick="posSystem.completeService('${entry.order.id}')">
                        <i class="fas fa-check"></i> Complete
                    </button>`;
        }
        return '';
    }
    
    // Service Management
    async startService(orderId) {
        try {
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/services/orders/${orderId}/start/`,
                { method: 'POST' }
            );
            
            if (response.success) {
                TabletBase.showToast('Service started', 'success');
                await this.refreshQueue();
            } else {
                TabletBase.showToast(response.message || 'Failed to start service', 'error');
            }
            
        } catch (error) {
            console.error('Error starting service:', error);
            TabletBase.showToast('Error starting service', 'error');
        }
    }
    
    async completeService(orderId) {
        try {
            const response = await TabletBase.apiRequest(
                `/business/${this.config.tenant_slug}/services/orders/${orderId}/complete/`,
                { method: 'POST' }
            );
            
            if (response.success) {
                TabletBase.showToast('Service completed', 'success');
                await this.refreshQueue();
            } else {
                TabletBase.showToast(response.message || 'Failed to complete service', 'error');
            }
            
        } catch (error) {
            console.error('Error completing service:', error);
            TabletBase.showToast('Error completing service', 'error');
        }
    }
    
    // Utility Methods
    async checkOut() {
        if (confirm('Are you sure you want to check out?')) {
            try {
                const response = await TabletBase.apiRequest(
                    `/business/${this.config.tenant_slug}/services/ajax/check-out/`,
                    { method: 'POST' }
                );
                
                if (response.success) {
                    TabletBase.showToast('Checked out successfully', 'success');
                    setTimeout(() => {
                        window.location.href = `/business/${this.config.tenant_slug}/`;
                    }, 2000);
                } else {
                    TabletBase.showToast(response.message || 'Failed to check out', 'error');
                }
                
            } catch (error) {
                console.error('Error checking out:', error);
                TabletBase.showToast('Error checking out', 'error');
            }
        }
    }
}

// Global functions for onclick handlers
window.posSystem = null;

// Make functions globally available
window.showCustomerModal = () => posSystem?.showCustomerModal();
window.showAddVehicleModal = () => posSystem?.showAddVehicleModal();
window.clearCustomer = () => posSystem?.clearCustomer();
window.clearCart = () => posSystem?.clearCart();
window.processPayment = () => posSystem?.processPayment();
window.refreshQueue = () => posSystem?.refreshQueue();
window.checkOut = () => posSystem?.checkOut();

// Payment processing functions
window.processExistingOrderPayment = (orderId, paymentMethod) => posSystem?.processExistingOrderPayment(orderId, paymentMethod);
window.completeOrder = (orderId) => posSystem?.completeOrder(orderId);
window.showPaymentModal = (orderId, orderTotal, customerName) => posSystem?.showPaymentModal(orderId, orderTotal, customerName);

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PosSystem;
}
