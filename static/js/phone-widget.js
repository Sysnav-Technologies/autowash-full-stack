// Phone Number Widget JavaScript with Search Functionality
document.addEventListener('DOMContentLoaded', function() {
    // Handle phone number input formatting and validation
    const phoneWidgets = document.querySelectorAll('.phone-number-widget');
    
    phoneWidgets.forEach(widget => {
        const countrySelect = widget.querySelector('.country-select');
        const phoneInput = widget.querySelector('.phone-number');
        
        if (countrySelect && phoneInput) {
            // Add modern interaction states
            addFocusStates(widget, countrySelect, phoneInput);
            
            // Add search functionality to country dropdown
            addCountrySearchFunctionality(countrySelect);
            
            // Update placeholder when country changes
            countrySelect.addEventListener('change', function() {
                updatePlaceholder(this.value, phoneInput);
                phoneInput.focus();
                clearValidationState(widget);
            });
            
            // Format phone number as user types
            phoneInput.addEventListener('input', function() {
                formatPhoneNumber(this);
                clearValidationState(widget);
            });
            
            // Validation on blur
            phoneInput.addEventListener('blur', function() {
                validatePhoneNumber(countrySelect.value, this.value, widget);
            });
            
            // Initialize placeholder
            updatePlaceholder(countrySelect.value, phoneInput);
        }
    });
    
    function addCountrySearchFunctionality(selectElement) {
        let searchTerm = '';
        let searchTimeout;
        
        selectElement.addEventListener('keydown', function(e) {
            // Clear previous timeout
            clearTimeout(searchTimeout);
            
            // Handle character input for search
            if (e.key.length === 1) {
                searchTerm += e.key.toLowerCase();
                
                // Add visual indicator
                this.classList.add('searching');
                
                // Find matching option
                const options = Array.from(this.options);
                const matchingOption = options.find(option => 
                    option.text.toLowerCase().includes(searchTerm)
                );
                
                if (matchingOption) {
                    this.value = matchingOption.value;
                    this.dispatchEvent(new Event('change'));
                }
                
                // Clear search term and visual indicator after 1 second
                searchTimeout = setTimeout(() => {
                    searchTerm = '';
                    this.classList.remove('searching');
                }, 1000);
                
                e.preventDefault();
            }
            // Handle backspace
            else if (e.key === 'Backspace') {
                searchTerm = searchTerm.slice(0, -1);
                if (searchTerm === '') {
                    this.classList.remove('searching');
                }
            }
            // Handle escape to clear search
            else if (e.key === 'Escape') {
                searchTerm = '';
                this.classList.remove('searching');
            }
        });
        
        // Add tooltip for search functionality
        selectElement.title = 'Type to search countries (e.g., "kenya", "usa", "uk")';
    }
    
    function addFocusStates(widget, countrySelect, phoneInput) {
        // Simple focus state management - no visual transforms
        countrySelect.addEventListener('focus', () => {
            widget.classList.add('country-focused');
        });
        
        countrySelect.addEventListener('blur', () => {
            widget.classList.remove('country-focused');
        });
        
        phoneInput.addEventListener('focus', () => {
            widget.classList.add('phone-focused');
        });
        
        phoneInput.addEventListener('blur', () => {
            widget.classList.remove('phone-focused');
        });
    }
    
    function updatePlaceholder(countryCode, phoneInput) {
        const placeholder = getPlaceholderForCountry(countryCode);
        phoneInput.placeholder = placeholder;
        phoneInput.setAttribute('data-country', countryCode);
    }
    
    function formatPhoneNumber(input) {
        let value = input.value.replace(/\D/g, ''); // Remove non-digits
        
        // Apply basic formatting based on country
        const countryCode = input.getAttribute('data-country');
        if (countryCode === 'US') {
            // US phone number formatting: (123) 456-7890
            if (value.length >= 6) {
                value = `(${value.slice(0, 3)}) ${value.slice(3, 6)}-${value.slice(6, 10)}`;
            } else if (value.length >= 3) {
                value = `(${value.slice(0, 3)}) ${value.slice(3)}`;
            }
        } else {
            // International formatting: just ensure digits
            value = value;
        }
        
        input.value = value.replace(/\D/g, ''); // Keep only digits for now
    }
    
    function clearValidationState(widget) {
        widget.classList.remove('is-invalid', 'is-valid');
    }
    
    function getPlaceholderForCountry(countryCode) {
        const placeholders = {
            'KE': '712 345 678',
            'UG': '712 345 678', 
            'TZ': '712 345 678',
            'US': '(202) 555-1234',
            'GB': '7123 456789',
            'IN': '98765 43210',
            'NG': '812 345 6789',
            'ZA': '82 123 4567',
            'EG': '123 456 7890',
            'AE': '50 123 4567',
            'SA': '50 123 4567'
        };
        return placeholders[countryCode] || '123 456 789';
    }
    
    function validatePhoneNumber(countryCode, phoneNumber, widget) {
        if (!phoneNumber) {
            widget.classList.remove('is-invalid', 'is-valid');
            return;
        }
        
        // Basic validation with country-specific rules
        const minLengths = {
            'KE': 9, 'UG': 9, 'TZ': 9, 'RW': 9,
            'US': 10, 'GB': 10, 'IN': 10,
            'NG': 10, 'ZA': 9, 'EG': 10,
            'AE': 9, 'SA': 9
        };
        
        const minLength = minLengths[countryCode] || 7;
        const maxLength = 15; // International standard
        
        const isValid = phoneNumber.length >= minLength && 
                       phoneNumber.length <= maxLength && 
                       /^\d+$/.test(phoneNumber);
        
        if (isValid) {
            widget.classList.remove('is-invalid');
            widget.classList.add('is-valid');
        } else {
            widget.classList.remove('is-valid');
            widget.classList.add('is-invalid');
        }
    }
    
    // Add smooth hover effects for better UX
    const style = document.createElement('style');
    style.textContent = `
        .phone-number-widget .country-select,
        .phone-number-widget .phone-number {
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }
        
        /* Search indicator */
        .country-select.searching {
            background-color: #e3f2fd;
        }
        
        /* Enhanced dropdown styling */
        .country-select option {
            padding: 8px 12px;
            font-size: 0.875rem;
        }
        
        .country-select option:hover {
            background-color: #f8f9fa;
        }
    `;
    document.head.appendChild(style);
});
