// static/js/pos-dashboard.js

// Global variables
let selectedPaymentMethod = null;
let currentPaymentId = null;
let selectedServiceOrder = null;
let refreshInterval = null;
let refreshCountdown = 30;

// Configuration
const CONFIG = {
    refreshInterval: 30000, // 30 seconds
    mpesaPollingInterval: 3000, // 3 seconds
    mpesaTimeout: 120000, // 2 minutes
    autoSaveInterval: 5000 // 5 seconds
};

// Initialize POS on page load
document.addEventListener('DOMContentLoaded', function() {
    initializePOS();
    startAutoRefresh();
    setupEventListeners();
    restoreFormData();
});

function initializePOS() {
    console.log('Initializing POS System...');
    
    // Load initial data
    refreshDashboard();
    
    // Setup keyboard shortcuts
    setupKeyboardShortcuts();
    
    // Check connectivity
    checkConnectivity();
}

function setupEventListeners() {
    // Form validation listeners
    const amountInput = document.getElementById('paymentAmount');
    const phoneInput = document.getElementById('customerPhone');
    const descriptionInput = document.getElementById('paymentDescription');
    
    if (amountInput) {
        amountInput.addEventListener('input', () => {
            validatePaymentForm();
            calculateFees();
            autoSaveFormData();
        });
        amountInput.addEventListener('blur', formatAmount);
    }
    
    if (phoneInput) {
        phoneInput.addEventListener('input', () => {
            validatePhoneNumber();
            autoSaveFormData();
        });
    }
    
    if (descriptionInput) {
        descriptionInput.addEventListener('input', autoSaveFormData);
    }
    
    // Modal event listeners
    setupModalListeners();
}

function setupModalListeners() {
    // Cash payment modal
    const cashModal = document.getElementById('cashPaymentModal');
    if (cashModal) {
        cashModal.addEventListener('shown.bs.modal', function() {
            document.getElementById('cashAmountTendered').focus();
        });
    }
    
    // M-Pesa modal
    const mpesaModal = document.getElementById('mpesaPaymentModal');
    if (mpesaModal) {
        mpesaModal.addEventListener('shown.bs.modal', function() {
            document.getElementById('mpesaPhoneNumber').focus();
        });
    }
    
    // Search modal
    const searchModal = document.getElementById('searchModal');
    if (searchModal) {
        searchModal.addEventListener('shown.bs.modal', function() {
            document.getElementById('searchInput').focus();
        });
    }
}

function startAutoRefresh() {
    refreshInterval = setInterval(() => {
        refreshCountdown--;
        const timerElement = document.getElementById('refreshTimer');
        if (timerElement) {
            timerElement.textContent = refreshCountdown;
        }
        
        if (refreshCountdown <= 0) {
            refreshDashboard();
            refreshCountdown = 30;
        }
    }, 1000);
}

function refreshDashboard() {
    showLoadingIndicator();
    
    fetch(`/business/${TENANT_SLUG}/payments/ajax/today-transactions/`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateTransactionsList(data.transactions);
                updateStats(data.totals);
                announceToScreenReader('Dashboard refreshed');
            }
        })
        .catch(error => {
            console.error('Error refreshing dashboard:', error);
            showToast('Error refreshing data', 'error');
        })
        .finally(() => {
            hideLoadingIndicator();
        });
}


function updateTransactionsList(transactions) {
    const container = document.getElementById('transactionsList');
    
    if (!container) return;
    
    if (transactions.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="fas fa-inbox fa-2x mb-2"></i>
                <div>No transactions today</div>
            </div>
        `;
        return;
    }
    
    container.innerHTML = transactions.map(transaction => `
        <div class="transaction-item fade-in" onclick="showPaymentDetails('${transaction.payment_id}')">
            <div class="transaction-info">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <strong>${transaction.payment_id}</strong>
                        <div class="text-muted small">${transaction.customer}</div>
                    </div>
                    <div class="text-end">
                        <div class="transaction-amount">KES ${transaction.amount.toFixed(2)}</div>
                        <span class="transaction-status status-${transaction.status}">
                            ${transaction.status_display}
                        </span>
                    </div>
                </div>
                <div class="text-muted small mt-1">
                    ${transaction.payment_method} • ${transaction.time}
                    ${transaction.can_verify ? '<span class="badge bg-warning ms-2">Verify</span>' : ''}
                </div>
            </div>
        </div>
    `).join('');
}

function updateStats(totals) {
    // Update stat cards if needed
    const elements = {
        todayRevenue: document.querySelector('.stat-value.text-success'),
        pendingCount: document.querySelector('.stat-value.text-warning'),
        totalCount: document.querySelector('.stat-value.text-primary')
    };
    
    if (elements.todayRevenue) {
        elements.todayRevenue.textContent = `KES ${totals.completed_amount.toFixed(0)}`;
    }
    if (elements.pendingCount) {
        elements.pendingCount.textContent = totals.pending_count;
    }
    if (elements.totalCount) {
        elements.totalCount.textContent = totals.completed_count;
    }
}

// ============================================================================
// SERVICE ORDER INTEGRATION
// ============================================================================

function createFromServiceOrder() {
    loadUnpaidOrders();
    const modal = new bootstrap.Modal(document.getElementById('unpaidOrdersModal'));
    modal.show();
}

function showUnpaidOrdersModal() {
    createFromServiceOrder();
}

function loadUnpaidOrders() {
    showLoadingIndicator();
    
    fetch(`/business/${TENANT_SLUG}/services/ajax/unpaid-orders/`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayUnpaidOrders(data.orders);
            } else {
                showToast('Error loading unpaid orders', 'error');
            }
        })
        .catch(error => {
            console.error('Error loading unpaid orders:', error);
            showToast('Error loading unpaid orders', 'error');
            // Fallback: show basic service order selection
            displayUnpaidOrdersFallback();
        })
        .finally(() => {
            hideLoadingIndicator();
        });
}

function displayServiceOrders(orders) {
    const container = document.getElementById('serviceOrdersContent');
    
    if (orders.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="fas fa-clipboard-list fa-2x mb-2"></i>
                <div>No pending service orders</div>
                <p class="small">Create a new service order first, then process payment.</p>
                <a href="/business/${window.location.pathname.split('/')[2]}/services/orders/quick/" class="btn btn-primary">
                    <i class="fas fa-plus me-2"></i>Create Service Order
                </a>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="row">
            ${orders.map(order => `
                <div class="col-md-6 mb-3">
                    <div class="service-order-card" onclick="selectServiceOrder('${order.id}')">
                        <div class="order-header">
                            <div>
                                <h6 class="mb-1">${order.order_number}</h6>
                                <div class="text-muted small">${order.customer_name}</div>
                            </div>
                            <span class="order-status ${order.status}">${order.status_display}</span>
                        </div>
                        <div class="d-flex justify-content-between align-items-end">
                            <div class="small text-muted">
                                ${order.vehicle_info}<br>
                                ${order.services_count} service(s)
                            </div>
                            <div class="text-end">
                                <div class="h6 text-success mb-0">KES ${order.total_amount.toFixed(2)}</div>
                                <div class="small text-muted">${order.payment_status_display}</div>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function displayServiceOrdersFallback() {
    const container = document.getElementById('serviceOrdersContent');
    container.innerHTML = `
        <div class="alert alert-info">
            <i class="fas fa-info-circle me-2"></i>
            <strong>Service Orders Integration</strong><br>
            Service orders integration is available. You can create payments directly from service orders.
        </div>
        <div class="text-center">
            <a href="/business/${window.location.pathname.split('/')[2]}/services/orders/" class="btn btn-primary">
                <i class="fas fa-external-link-alt me-2"></i>Go to Service Orders
            </a>
        </div>
    `;
}

function selectServiceOrder(orderId) {
    const tenantSlug = window.location.pathname.split('/')[2];
    
    fetch(`/business/${tenantSlug}/services/ajax/order/${orderId}/`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const order = data.order;
                selectedServiceOrder = order;
                
                // Pre-fill payment form
                document.getElementById('paymentAmount').value = order.total_amount;
                document.getElementById('paymentDescription').value = `Payment for service order ${order.order_number}`;
                
                if (order.customer.phone) {
                    document.getElementById('customerPhone').value = order.customer.phone;
                }
                
                // Close modal and validate form
                bootstrap.Modal.getInstance(document.getElementById('serviceOrdersModal')).hide();
                validatePaymentForm();
                calculateFees();
                
                showToast(`Loaded service order ${order.order_number}`, 'success');
            }
        })
        .catch(error => {
            console.error('Error loading service order:', error);
            showToast('Error loading service order details', 'error');
        });
}

// Payment Processing Functions
function setQuickAmount(amount) {
    // Clear previous selection
    document.querySelectorAll('.quick-amount-btn').forEach(btn => {
        btn.classList.remove('selected');
    });
    
    // Set amount and select button
    document.getElementById('paymentAmount').value = amount;
    event.target.classList.add('selected');
    
    // Trigger validation and fee calculation
    calculateFees();
    validatePaymentForm();
    autoSaveFormData();
}

function selectPaymentMethod(methodId, methodType) {
    // Clear previous selection
    document.querySelectorAll('.method-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Select current method
    const methodCard = document.querySelector(`[data-method-id="${methodId}"]`);
    if (methodCard) {
        methodCard.classList.add('selected');
    }
    
    selectedPaymentMethod = {
        id: methodId,
        type: methodType
    };
    
    // Calculate fees for this method
    calculateFees();
    validatePaymentForm();
    autoSaveFormData();
}

function calculateFees() {
    const amount = parseFloat(document.getElementById('paymentAmount').value) || 0;
    
    if (!selectedPaymentMethod || amount <= 0) {
        document.getElementById('feeDisplay').style.display = 'none';
        return;
    }
    
    const tenantSlug = window.location.pathname.split('/')[2];
    
    fetch(`/business/${tenantSlug}/payments/ajax/calculate-fees/?amount=${amount}&method_id=${selectedPaymentMethod.id}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('processingFee').textContent = `KES ${data.processing_fee.toFixed(2)}`;
                document.getElementById('netAmount').textContent = `KES ${data.net_amount.toFixed(2)}`;
                document.getElementById('feeDisplay').style.display = data.processing_fee > 0 ? 'block' : 'none';
                
                if (!data.is_valid) {
                    showToast(data.validation_message, 'warning');
                }
            }
        })
        .catch(error => {
            console.error('Error calculating fees:', error);
        });
}

function validatePaymentForm() {
    const amount = parseFloat(document.getElementById('paymentAmount').value) || 0;
    const hasMethod = selectedPaymentMethod !== null;
    const isValid = amount > 0 && hasMethod;
    
    const btn = document.getElementById('processPaymentBtn');
    btn.disabled = !isValid;
    
    if (isValid) {
        btn.innerHTML = `
            <i class="fas fa-credit-card me-2"></i>
            Process Payment (KES ${amount.toFixed(2)})
        `;
        btn.classList.remove('btn-secondary');
        btn.classList.add('btn-success');
    } else {
        btn.innerHTML = `
            <i class="fas fa-credit-card me-2"></i>
            Process Payment
        `;
        btn.classList.remove('btn-success');
        btn.classList.add('btn-secondary');
    }
}

function validatePhoneNumber() {
    const phoneInput = document.getElementById('customerPhone');
    const phone = phoneInput.value;
    
    if (!phone) {
        phoneInput.classList.remove('is-valid', 'is-invalid');
        return;
    }
    
    // Kenyan phone number validation
    const cleaned = phone.replace(/\D/g, '');
    const kenyanRegex = /^(254|0)?[17]\d{8}$/;
    const isValid = kenyanRegex.test(cleaned);
    
    phoneInput.classList.toggle('is-invalid', !isValid);
    phoneInput.classList.toggle('is-valid', isValid);
    
    return isValid;
}

function formatAmount() {
    const input = document.getElementById('paymentAmount');
    const value = parseFloat(input.value);
    if (!isNaN(value)) {
        input.value = value.toFixed(2);
        calculateFees();
    }
}

function processPayment() {
    const amount = parseFloat(document.getElementById('paymentAmount').value);
    const phone = document.getElementById('customerPhone').value;
    const description = document.getElementById('paymentDescription').value;
    
    if (!selectedPaymentMethod || amount <= 0) {
        showToast('Please enter amount and select payment method', 'error');
        return;
    }
    
    // Validate phone if provided
    if (phone && !validatePhoneNumber()) {
        showToast('Please enter a valid phone number', 'error');
        return;
    }
    
    // Show loading state
    const btn = document.getElementById('processPaymentBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<div class="spinner"></div>Creating payment...';
    btn.disabled = true;
    
    const tenantSlug = window.location.pathname.split('/')[2];
    
    const paymentData = {
        amount: amount,
        payment_method_id: selectedPaymentMethod.id,
        customer_phone: phone,
        description: description || 'POS Payment'
    };
    
    // Add service order if selected
    if (selectedServiceOrder) {
        paymentData.order_id = selectedServiceOrder.id;
    }
    
    // Create payment
    fetch(`/business/${tenantSlug}/payments/ajax/create-payment/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(paymentData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            currentPaymentId = data.payment_id;
            
            // Route to appropriate payment method
            switch (data.next_action) {
                case 'cash':
                    showCashPaymentModal(data.payment_data);
                    break;
                case 'mpesa':
                    showMpesaPaymentModal(data.payment_data);
                    break;
                case 'card':
                    showCardPaymentModal(data.payment_data);
                    break;
                default:
                    showToast('Payment created successfully', 'success');
                    clearPaymentForm();
                    refreshDashboard();
            }
        } else {
            showToast(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error creating payment:', error);
        showToast('Error creating payment', 'error');
    })
    .finally(() => {
        btn.innerHTML = originalText;
        validatePaymentForm();
    });
}

// Cash Payment Functions
function showCashPaymentModal(paymentData) {
    document.getElementById('cashAmountTendered').value = paymentData.amount;
    calculateCashChange();
    
    const modal = new bootstrap.Modal(document.getElementById('cashPaymentModal'));
    modal.show();
}

function calculateCashChange() {
    const amount = parseFloat(document.getElementById('paymentAmount').value) || 0;
    const tendered = parseFloat(document.getElementById('cashAmountTendered').value) || 0;
    const change = Math.max(0, tendered - amount);
    
    document.getElementById('cashChangeDue').value = change.toFixed(2);
    
    if (change > 0) {
        document.getElementById('changeAmount').textContent = `KES ${change.toFixed(2)}`;
        document.getElementById('cashChangeDisplay').style.display = 'block';
        suggestChange(change);
    } else {
        document.getElementById('cashChangeDisplay').style.display = 'none';
    }
    
    // Enable/disable complete button
    const btn = document.getElementById('completeCashBtn');
    btn.disabled = tendered < amount;
    
    if (tendered < amount) {
        btn.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Insufficient Amount';
        btn.className = 'btn btn-danger';
    } else {
        btn.innerHTML = '<i class="fas fa-check me-2"></i>Complete Payment';
        btn.className = 'btn btn-success';
    }
}

function suggestChange(amount) {
    const denominations = [1000, 500, 200, 100, 50, 40, 20, 10, 5, 1];
    let remaining = amount;
    let suggestion = [];
    
    for (let denom of denominations) {
        if (remaining >= denom) {
            const count = Math.floor(remaining / denom);
            suggestion.push(`${count} × KES ${denom}`);
            remaining -= count * denom;
            remaining = Math.round(remaining * 100) / 100;
        }
    }
    
    document.getElementById('changeSuggestion').innerHTML = 
        suggestion.length > 0 ? `Suggested: ${suggestion.join(', ')}` : '';
}

function completeCashPayment() {
    const tendered = parseFloat(document.getElementById('cashAmountTendered').value);
    const amount = parseFloat(document.getElementById('paymentAmount').value);
    
    if (tendered < amount) {
        showToast('Insufficient amount tendered', 'error');
        return;
    }
    
    const btn = document.getElementById('completeCashBtn');
    btn.innerHTML = '<div class="spinner"></div>Processing...';
    btn.disabled = true;
    
    const tenantSlug = window.location.pathname.split('/')[2];
    
    fetch(`/business/${tenantSlug}/payments/ajax/process-cash/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            payment_id: currentPaymentId,
            amount_tendered: tendered
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Cash payment completed successfully', 'success');
            showReceiptModal(data.receipt_data);
            
            // Close modal and clear form
            bootstrap.Modal.getInstance(document.getElementById('cashPaymentModal')).hide();
            clearPaymentForm();
            refreshDashboard();
            clearAutoSaveData();
        } else {
            showToast(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error processing cash payment:', error);
        showToast('Error processing payment', 'error');
    })
    .finally(() => {
        btn.innerHTML = '<i class="fas fa-check me-2"></i>Complete Payment';
        btn.disabled = false;
        btn.className = 'btn btn-success';
    });
}

// M-Pesa Payment Functions
function showMpesaPaymentModal(paymentData) {
    // Pre-fill phone if available
    if (paymentData.customer_phone) {
        const phone = paymentData.customer_phone.replace(/^\+254/, '').replace(/^0/, '');
        document.getElementById('mpesaPhoneNumber').value = phone;
    }
    
    // Reset modal state
    document.getElementById('mpesaStatus').style.display = 'none';
    document.getElementById('sendMpesaBtn').disabled = false;
    
    const modal = new bootstrap.Modal(document.getElementById('mpesaPaymentModal'));
    modal.show();
}

function sendMpesaRequest() {
    const phone = document.getElementById('mpesaPhoneNumber').value;
    
    if (!phone || phone.length < 9) {
        showToast('Please enter a valid phone number', 'error');
        return;
    }
    
    // Show status
    document.getElementById('mpesaStatus').style.display = 'block';
    document.getElementById('mpesaStatusMessage').textContent = 'Sending payment request...';
    
    const btn = document.getElementById('sendMpesaBtn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div>Sending...';
    
    const tenantSlug = window.location.pathname.split('/')[2];
    
    fetch(`/business/${tenantSlug}/payments/ajax/process-mpesa/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            payment_id: currentPaymentId,
            phone_number: phone
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('mpesaStatusMessage').textContent = 
                'STK push sent! Please enter your M-Pesa PIN on your phone.';
            
            // Start polling for payment status
            pollMpesaStatus(data.payment_id);
        } else {
            showToast(data.message, 'error');
            document.getElementById('mpesaStatus').style.display = 'none';
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Send M-Pesa Request';
        }
    })
    .catch(error => {
        console.error('Error sending M-Pesa request:', error);
        showToast('Error sending M-Pesa request', 'error');
        document.getElementById('mpesaStatus').style.display = 'none';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Send M-Pesa Request';
    });
}

function pollMpesaStatus(paymentId) {
    const tenantSlug = window.location.pathname.split('/')[2];
    let pollCount = 0;
    const maxPolls = CONFIG.mpesaTimeout / CONFIG.mpesaPollingInterval;
    
    const pollInterval = setInterval(() => {
        pollCount++;
        
        fetch(`/business/${tenantSlug}/payments/ajax/mpesa-poll/${paymentId}/`)
            .then(response => response.json())
            .then(data => {
                document.getElementById('mpesaStatusMessage').textContent = data.message;
                
                if (data.should_stop_polling) {
                    clearInterval(pollInterval);
                    
                    if (data.status === 'completed') {
                        showToast('M-Pesa payment completed successfully', 'success');
                        bootstrap.Modal.getInstance(document.getElementById('mpesaPaymentModal')).hide();
                        clearPaymentForm();
                        refreshDashboard();
                        clearAutoSaveData();
                    } else if (data.status === 'failed') {
                        showToast('M-Pesa payment failed', 'error');
                        document.getElementById('sendMpesaBtn').disabled = false;
                        document.getElementById('sendMpesaBtn').innerHTML = '<i class="fas fa-paper-plane me-2"></i>Retry M-Pesa Request';
                    }
                }
                
                // Timeout after max polls
                if (pollCount >= maxPolls) {
                    clearInterval(pollInterval);
                    document.getElementById('mpesaStatusMessage').textContent = 
                        'Payment verification timed out. Please check manually.';
                    document.getElementById('sendMpesaBtn').disabled = false;
                    document.getElementById('sendMpesaBtn').innerHTML = '<i class="fas fa-paper-plane me-2"></i>Send M-Pesa Request';
                }
            })
            .catch(error => {
                console.error('Error polling M-Pesa status:', error);
                clearInterval(pollInterval);
                document.getElementById('mpesaStatusMessage').textContent = 
                    'Error checking payment status. Please verify manually.';
            });
    }, CONFIG.mpesaPollingInterval);
}

// Card Payment Functions
function showCardPaymentModal(paymentData) {
    // For now, simulate card payment
    // In a real implementation, you'd integrate with a card processor
    showToast('Card payment integration coming soon', 'info');
    
    // Simulate successful card payment after 2 seconds
    setTimeout(() => {
        const receiptData = {
            payment_id: currentPaymentId,
            amount: paymentData.amount,
            customer: 'Card Customer',
            timestamp: new Date().toISOString(),
            payment_method: 'Card'
        };
        
        showToast('Card payment completed successfully', 'success');
        showReceiptModal(receiptData);
        clearPaymentForm();
        refreshDashboard();
        clearAutoSaveData();
    }, 2000);
}

// Payment Details and Receipt Functions
function showPaymentDetails(paymentId) {
    const tenantSlug = window.location.pathname.split('/')[2];
    
    fetch(`/business/${tenantSlug}/payments/ajax/payment/${paymentId}/`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const payment = data.payment;
                document.getElementById('paymentDetailsContent').innerHTML = generatePaymentDetailsHTML(payment);
                
                const modal = new bootstrap.Modal(document.getElementById('paymentDetailsModal'));
                modal.show();
            }
        })
        .catch(error => {
            console.error('Error loading payment details:', error);
            showToast('Error loading payment details', 'error');
        });
}

function generatePaymentDetailsHTML(payment) {
    return `
        <div class="row">
            <div class="col-md-6">
                <h6>Payment Information</h6>
                <table class="table table-sm">
                    <tr><td>Payment ID:</td><td><strong>${payment.payment_id}</strong></td></tr>
                    <tr><td>Amount:</td><td><strong>KES ${payment.amount.toFixed(2)}</strong></td></tr>
                    <tr><td>Status:</td><td><span class="badge bg-${getStatusColor(payment.status)}">${payment.status_display}</span></td></tr>
                    <tr><td>Method:</td><td>${payment.payment_method}</td></tr>
                    <tr><td>Created:</td><td>${formatDateTime(payment.created_at)}</td></tr>
                    ${payment.completed_at ? `<tr><td>Completed:</td><td>${formatDateTime(payment.completed_at)}</td></tr>` : ''}
                </table>
            </div>
            <div class="col-md-6">
                <h6>Customer Information</h6>
                <table class="table table-sm">
                    <tr><td>Customer:</td><td>${payment.customer || 'Walk-in'}</td></tr>
                    ${payment.service_order ? `<tr><td>Service Order:</td><td>${payment.service_order}</td></tr>` : ''}
                    <tr><td>Description:</td><td>${payment.description || '-'}</td></tr>
                </table>
                
                <div class="mt-3">
                    ${payment.status === 'completed' ? `
                        <button class="btn btn-outline-success btn-sm me-2" onclick="verifyPayment('${payment.payment_id}')">
                            <i class="fas fa-check me-2"></i>Verify Payment
                        </button>
                    ` : ''}
                    
                    <button class="btn btn-outline-primary btn-sm" onclick="generateReceipt('${payment.payment_id}')">
                        <i class="fas fa-receipt me-2"></i>Generate Receipt
                    </button>
                </div>
            </div>
        </div>
    `;
}

function verifyPayment(paymentId) {
    const tenantSlug = window.location.pathname.split('/')[2];
    
    fetch(`/business/${tenantSlug}/payments/ajax/payment/${paymentId}/verify/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Payment verified successfully', 'success');
            bootstrap.Modal.getInstance(document.getElementById('paymentDetailsModal')).hide();
            refreshDashboard();
        } else {
            showToast(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error verifying payment:', error);
        showToast('Error verifying payment', 'error');
    });
}

function generateReceipt(paymentId) {
    const tenantSlug = window.location.pathname.split('/')[2];
    
    fetch(`/business/${tenantSlug}/payments/ajax/receipt/${paymentId}/`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('receiptContent').innerHTML = data.receipt_html;
                bootstrap.Modal.getInstance(document.getElementById('paymentDetailsModal')).hide();
                
                const modal = new bootstrap.Modal(document.getElementById('receiptModal'));
                modal.show();
            }
        })
        .catch(error => {
            console.error('Error generating receipt:', error);
            showToast('Error generating receipt', 'error');
        });
}

function showReceiptModal(receiptData) {
    const receiptHtml = generateReceiptHTML(receiptData);
    document.getElementById('receiptContent').innerHTML = receiptHtml;
    
    const modal = new bootstrap.Modal(document.getElementById('receiptModal'));
    modal.show();
}

function generateReceiptHTML(receiptData) {
    return `
        <div class="receipt">
            <div class="receipt-header">
                <h6>Payment Receipt</h6>
                <div class="small text-muted">Thank you for your business!</div>
            </div>
            
            <div class="receipt-item">
                <span>Receipt #:</span>
                <span>${receiptData.payment_id}</span>
            </div>
            <div class="receipt-item">
                <span>Date:</span>
                <span>${formatDateTime(receiptData.timestamp)}</span>
            </div>
            <div class="receipt-item">
                <span>Customer:</span>
                <span>${receiptData.customer}</span>
            </div>
            ${receiptData.cashier ? `
            <div class="receipt-item">
                <span>Cashier:</span>
                <span>${receiptData.cashier}</span>
            </div>
            ` : ''}
            
            <div class="receipt-total">
                <div class="receipt-item">
                    <span>Amount:</span>
                    <span>KES ${receiptData.amount.toFixed(2)}</span>
                </div>
                ${receiptData.amount_tendered ? `
                <div class="receipt-item">
                    <span>Tendered:</span>
                    <span>KES ${receiptData.amount_tendered.toFixed(2)}</span>
                </div>
                <div class="receipt-item">
                    <span>Change:</span>
                    <span>KES ${receiptData.change_given.toFixed(2)}</span>
                </div>
                ` : ''}
            </div>
            
            <div class="text-center mt-3">
                <div class="small">Thank you for your business!</div>
            </div>
        </div>
    `;
}

function printReceipt() {
    const receiptContent = document.getElementById('receiptContent').innerHTML;
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <html>
            <head>
                <title>Receipt</title>
                <style>
                    body { font-family: 'Courier New', monospace; margin: 0; padding: 20px; }
                    .receipt { max-width: 300px; margin: 0 auto; }
                    .receipt-header { text-align: center; border-bottom: 1px dashed #ccc; padding-bottom: 10px; margin-bottom: 10px; }
                    .receipt-item { display: flex; justify-content: space-between; margin-bottom: 5px; }
                    .receipt-total { border-top: 1px dashed #ccc; padding-top: 10px; margin-top: 10px; }
                </style>
            </head>
            <body>
                ${receiptContent}
            </body>
        </html>
    `);
    printWindow.document.close();
    printWindow.print();
}

// Search Functions
function showSearchModal() {
    const modal = new bootstrap.Modal(document.getElementById('searchModal'));
    modal.show();
}

function searchPayments() {
    const query = document.getElementById('searchInput').value;
    
    if (query.length < 2) {
        document.getElementById('searchResults').innerHTML = '';
        return;
    }
    
    const tenantSlug = window.location.pathname.split('/')[2];
    
    fetch(`/business/${tenantSlug}/payments/ajax/search-payments/?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const results = data.payments.map(payment => `
                    <div class="border rounded p-3 mb-2 cursor-pointer" onclick="showPaymentDetails('${payment.payment_id}')">
                        <div class="d-flex justify-content-between">
                            <div>
                                <strong>${payment.payment_id}</strong>
                                <div class="text-muted small">${payment.customer}</div>
                            </div>
                            <div class="text-end">
                                <div class="text-success"><strong>KES ${payment.amount.toFixed(2)}</strong></div>
                                <span class="badge bg-${getStatusColor(payment.status)}">${payment.status_display}</span>
                            </div>
                        </div>
                        <div class="text-muted small mt-1">
                            ${payment.payment_method} • ${payment.date}
                        </div>
                    </div>
                `).join('');
                
                document.getElementById('searchResults').innerHTML = results || 
                    '<div class="text-center text-muted">No payments found</div>';
            }
        })
        .catch(error => {
            console.error('Error searching payments:', error);
        });
}

// Form Management Functions
function clearPaymentForm() {
    document.getElementById('paymentForm').reset();
    document.querySelectorAll('.method-card').forEach(card => card.classList.remove('selected'));
    document.querySelectorAll('.quick-amount-btn').forEach(btn => btn.classList.remove('selected'));
    document.getElementById('feeDisplay').style.display = 'none';
    
    selectedPaymentMethod = null;
    currentPaymentId = null;
    selectedServiceOrder = null;
    
    // Clear validation states
    document.querySelectorAll('.form-control').forEach(input => {
        input.classList.remove('is-valid', 'is-invalid');
    });
    
    validatePaymentForm();
    clearAutoSaveData();
}

function filterTransactions(status) {
    // For now, just refresh to show all
    // In a more advanced implementation, you'd filter the display
    refreshDashboard();
}

// Auto-save Functions
function autoSaveFormData() {
    const formData = {
        amount: document.getElementById('paymentAmount').value,
        phone: document.getElementById('customerPhone').value,
        description: document.getElementById('paymentDescription').value,
        selectedMethod: selectedPaymentMethod,
        selectedServiceOrder: selectedServiceOrder,
        timestamp: Date.now()
    };
    
    try {
        localStorage.setItem('pos_form_data', JSON.stringify(formData));
    } catch (error) {
        console.warn('Failed to auto-save form data:', error);
    }
}

function restoreFormData() {
    try {
        const saved = localStorage.getItem('pos_form_data');
        if (saved) {
            const data = JSON.parse(saved);
            
            // Only restore if data is recent (less than 1 hour old)
            if (Date.now() - (data.timestamp || 0) < 3600000) {
                document.getElementById('paymentAmount').value = data.amount || '';
                document.getElementById('customerPhone').value = data.phone || '';
                document.getElementById('paymentDescription').value = data.description || '';
                
                if (data.selectedMethod) {
                    selectPaymentMethod(data.selectedMethod.id, data.selectedMethod.type);
                }
                
                if (data.selectedServiceOrder) {
                    selectedServiceOrder = data.selectedServiceOrder;
                }
                
                validatePaymentForm();
                calculateFees();
            }
        }
    } catch (error) {
        console.warn('Failed to restore form data:', error);
    }
}

function clearAutoSaveData() {
    try {
        localStorage.removeItem('pos_form_data');
    } catch (error) {
        console.warn('Failed to clear auto-save data:', error);
    }
}

// Utility Functions
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
           document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
}

function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

function getStatusColor(status) {
    const colors = {
        'completed': 'success',
        'verified': 'primary',
        'pending': 'warning',
        'processing': 'info',
        'failed': 'danger',
        'cancelled': 'secondary'
    };
    return colors[status] || 'secondary';
}

function showToast(message, type = 'info') {
    const toastContainer = document.querySelector('.toast-container');
    const toastId = 'toast-' + Date.now();
    
    const bgClass = type === 'error' ? 'bg-danger' : 
                   type === 'success' ? 'bg-success' : 
                   type === 'warning' ? 'bg-warning' : 'bg-primary';
    
    const iconClass = type === 'error' ? 'exclamation-triangle' : 
                     type === 'success' ? 'check-circle' : 
                     type === 'warning' ? 'exclamation-triangle' : 'info-circle';
    
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${iconClass} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay: 5000 });
    toast.show();
    
    // Remove toast element after it's hidden
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
    
    // Announce to screen readers
    announceToScreenReader(message);
}

function showLoadingIndicator() {
    const indicator = document.getElementById('refreshIndicator');
    if (indicator) {
        indicator.style.display = 'inline-block';
    }
}

function hideLoadingIndicator() {
    const indicator = document.getElementById('refreshIndicator');
    if (indicator) {
        indicator.style.display = 'none';
    }
}

function announceToScreenReader(message) {
    const announcement = document.createElement('div');
    announcement.setAttribute('aria-live', 'polite');
    announcement.setAttribute('aria-atomic', 'true');
    announcement.style.cssText = 'position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden;';
    announcement.textContent = message;
    
    document.body.appendChild(announcement);
    
    setTimeout(() => {
        document.body.removeChild(announcement);
    }, 1000);
}

function checkConnectivity() {
    const tenantSlug = window.location.pathname.split('/')[2];
    
    return fetch(`/business/${tenantSlug}/payments/ajax/summary/`, {
        method: 'HEAD',
        cache: 'no-cache'
    }).then(() => true).catch(() => false);
}

// Keyboard Shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // ESC to clear form
        if (e.key === 'Escape') {
            clearPaymentForm();
        }
        
        // Ctrl/Cmd + R to refresh
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            e.preventDefault();
            refreshDashboard();
        }
        
        // Ctrl/Cmd + F to search
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
            e.preventDefault();
            showSearchModal();
        }
        
        // Quick amount shortcuts (Alt + number)
        if (e.altKey && e.key >= '1' && e.key <= '4') {
            e.preventDefault();
            const amounts = [500, 1000, 2000, 5000];
            setQuickAmount(amounts[parseInt(e.key) - 1]);
        }
        
        // Enter to process payment when form is valid
        if (e.key === 'Enter' && !e.target.closest('.modal') && !document.getElementById('processPaymentBtn').disabled) {
            e.preventDefault();
            processPayment();
        }
    });
}

// Network Status Handling
window.addEventListener('offline', function() {
    showToast('Connection lost. Please check your internet connection.', 'error');
    document.getElementById('processPaymentBtn').disabled = true;
});

window.addEventListener('online', function() {
    showToast('Connection restored.', 'success');
    validatePaymentForm();
    refreshDashboard();
});

// Error Handling
window.addEventListener('error', function(e) {
    console.error('JavaScript error:', e.error);
    showToast('An unexpected error occurred. Please refresh the page.', 'error');
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
    autoSaveFormData();
});

// Reports placeholder
function showReports() {
    showToast('Reports feature coming soon', 'info');
}

function showPaymentMethodBreakdown() {
    showToast('Payment method breakdown feature coming soon', 'info');
}

// Debug mode for development
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.POS_DEBUG = {
        refreshDashboard,
        selectedPaymentMethod,
        currentPaymentId,
        selectedServiceOrder,
        validatePaymentForm,
        clearPaymentForm,
        CONFIG
    };
    
    console.log('POS Debug mode enabled. Access window.POS_DEBUG for debugging.');
}