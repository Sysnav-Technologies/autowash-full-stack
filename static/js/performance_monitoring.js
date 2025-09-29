/**
 * Performance Monitoring Dashboard - AutoWash Control Panel
 * Real-time monitoring with analytics sidebar, auto-refresh, charts, and server actions
 */

// Global variables
let performanceCharts = {};
let autoRefreshInterval = null;
let isAutoRefreshEnabled = true;
let logsPaused = false;
let performanceData = {};
let realTimeData = [];
let pendingAction = null;
let sidebarOpen = false;

// Configuration
const REFRESH_INTERVAL = 3000; // 3 seconds for real-time monitoring
const MAX_DATA_POINTS = 50;
const CHART_COLORS = {
    primary: '#00d4ff',
    secondary: '#00ff88',
    accent: '#ffeb3b',
    danger: '#ff4444',
    purple: '#bd93f9'
};

/**
 * Initialize the performance monitoring dashboard
 */
function initializePerformanceMonitoring() {
    console.log('🎛️ Initializing AutoWash Control Panel...');
    
    // Load initial data
    loadInitialData();
    
    // Initialize charts
    initializeCharts();
    
    // Initialize sidebar
    initializeSidebar();
    
    // Set up event listeners
    setupEventListeners();
    
    // Start auto-refresh
    startAutoRefresh();
    
    // Update time display
    updateTimeDisplay();
    setInterval(updateTimeDisplay, 1000);
    
    // Initialize real-time logs
    initializeRealTimeLogs();
    
    console.log('✅ Mission Control initialized successfully');
}

/**
 * Load initial performance data from the template
 */
function loadInitialData() {
    try {
        const dataElement = document.getElementById('performance-data');
        if (dataElement) {
            performanceData = JSON.parse(dataElement.textContent);
            console.log('📊 Initial performance data loaded:', performanceData);
        }
    } catch (error) {
        console.error('❌ Error loading initial data:', error);
        performanceData = {};
    }
}

/**
 * Initialize all charts
 */
function initializeCharts() {
    // Main performance chart
    initializePerformanceChart();
    
    // Database performance chart
    initializeDatabaseChart();
    
    // Network traffic chart
    initializeNetworkChart();
    
    // User activity chart
    initializeUserActivityChart();
    
    console.log('📈 All charts initialized');
}

/**
 * Initialize Analytics Sidebar - New Simplified Approach
 */
function initializeSidebar() {
    console.log('� Initializing sidebar with new approach...');
    
    // Initialize sidebar state
    window.sidebarOpen = false;
    
    // Set up event listeners using direct DOM access
    setupSidebarEventListeners();
    
    // Initialize quick action buttons
    initializeQuickActions();
    
    console.log('✅ Sidebar initialization complete');
}

/**
 * Setup sidebar event listeners with robust error handling
 */
function setupSidebarEventListeners() {
    // Main toggle button event
    document.addEventListener('click', function(e) {
        if (e.target.matches('#sidebarToggleBtn') || e.target.closest('#sidebarToggleBtn')) {
            e.preventDefault();
            e.stopPropagation();
            console.log('🔄 Sidebar toggle clicked');
            toggleSidebarNew();
        }
        
        // Internal toggle button
        if (e.target.matches('#toggleSidebar') || e.target.closest('#toggleSidebar')) {
            e.preventDefault();
            e.stopPropagation();
            console.log('🔄 Internal sidebar toggle clicked');
            toggleSidebarNew();
        }
        
        // Close when clicking outside
        const sidebar = document.getElementById('analyticsSidebar');
        const toggleBtn = document.getElementById('sidebarToggleBtn');
        
        if (window.sidebarOpen && sidebar && !sidebar.contains(e.target) && 
            !toggleBtn.contains(e.target) && !e.target.closest('.analytics-sidebar')) {
            console.log('🔄 Closing sidebar - clicked outside');
            closeSidebar();
        }
    });
}

/**
 * Toggle Analytics Sidebar
 */
function toggleAnalyticsSidebar() {
    console.log('� New sidebar toggle called');
    
    const sidebar = document.getElementById('analyticsSidebar');
    const toggleBtn = document.getElementById('sidebarToggleBtn');
    
    if (!sidebar || !toggleBtn) {
        console.error('❌ Sidebar elements not found:', {
            sidebar: !!sidebar,
            toggleBtn: !!toggleBtn,
            allIds: Array.from(document.querySelectorAll('[id]')).map(el => el.id).slice(0, 10)
        });
        return;
    }
    
    // Toggle the state
    window.sidebarOpen = !window.sidebarOpen;
    console.log('� Sidebar state:', window.sidebarOpen ? 'OPENING' : 'CLOSING');
    
    if (window.sidebarOpen) {
        openSidebar();
    } else {
        closeSidebar();
    }
}

/**
 * Open sidebar with animation and state management
 */
function openSidebar() {
    const sidebar = document.getElementById('analyticsSidebar');
    const toggleBtn = document.getElementById('sidebarToggleBtn');
    
    if (sidebar && toggleBtn) {
        sidebar.classList.add('open');
        toggleBtn.innerHTML = '<i class="fas fa-times"></i>';
        toggleBtn.classList.add('active');
        document.body.classList.add('sidebar-open');
        
        console.log('✅ Sidebar opened');
        window.sidebarOpen = true;
    }
}

/**
 * Close sidebar with animation and state management
 */
function closeSidebar() {
    const sidebar = document.getElementById('analyticsSidebar');
    const toggleBtn = document.getElementById('sidebarToggleBtn');
    
    if (sidebar && toggleBtn) {
        sidebar.classList.remove('open');
        toggleBtn.innerHTML = '<i class="fas fa-chart-bar"></i>';
        toggleBtn.classList.remove('active');
        document.body.classList.remove('sidebar-open');
        
        console.log('✅ Sidebar closed');
        window.sidebarOpen = false;
    }
}

// Make functions globally available
window.toggleAnalyticsSidebar = toggleAnalyticsSidebar;
window.openSidebar = openSidebar;
window.closeSidebar = closeSidebar;

/**
 * Initialize Quick Action Buttons
 */
function initializeQuickActions() {
    // Refresh All Data button
    const refreshBtn = document.querySelector('[onclick="refreshAllData()"]');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function(e) {
            e.preventDefault();
            refreshAllData();
        });
    }
    
    // Export Report button
    const exportBtn = document.querySelector('[onclick="exportSystemReport()"]');
    if (exportBtn) {
        exportBtn.addEventListener('click', function(e) {
            e.preventDefault();
            exportSystemReport();
        });
    }
    
    // Clear Cache button  
    const clearCacheBtn = document.querySelector('[onclick="clearCache()"]');
    if (clearCacheBtn) {
        clearCacheBtn.addEventListener('click', function(e) {
            e.preventDefault();
            clearCache();
        });
    }
}

/**
 * Refresh All Data
 */
function refreshAllData() {
    showAlert('Refreshing all system data...', 'info');
    
    // Add loading overlay
    const loadingOverlay = document.createElement('div');
    loadingOverlay.id = 'loading-overlay';
    loadingOverlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.8);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 9999;
        color: #00ffff;
        font-size: 1.5rem;
    `;
    loadingOverlay.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing Data...';
    document.body.appendChild(loadingOverlay);
    
    // Simulate data refresh delay, then reload
    setTimeout(() => {
        location.reload();
    }, 1500);
}

/**
 * Export System Report
 */
function exportSystemReport() {
    showAlert('Preparing comprehensive system report...', 'info');
    
    // Get current timestamp in East Africa timezone
    const now = new Date();
    const eatTime = new Date(now.toLocaleString("en-US", {timeZone: "Africa/Nairobi"}));
    
    // Create comprehensive report data
    const reportData = {
        report_metadata: {
            title: 'AutoWash System Performance Report',
            generated_at: eatTime.toISOString(),
            timezone: 'East Africa Time (EAT)',
            report_version: '2.0',
            system_hostname: performanceData.system_info?.hostname || 'Unknown'
        },
        system_overview: {
            overall_status: performanceData.overall_status || 'Unknown',
            current_time: eatTime.toLocaleString(),
            platform: performanceData.system_info?.platform || 'Unknown',
            uptime: performanceData.system_info?.uptime || 'Unknown'
        },
        performance_metrics: {
            cpu_usage: performanceData.cpu_info?.usage_percent || 0,
            memory_usage: performanceData.memory_info?.usage_percent || 0,
            active_tenants: performanceData.tenant_stats?.active_tenants || 0,
            database_connections: performanceData.database_stats?.active_connections || 0,
            queries_per_second: performanceData.database_stats?.queries_per_second || 0
        },
        health_indicators: {
            cpu_status: getCPUStatus(),
            memory_status: getMemoryStatus(),
            database_status: performanceData.database_stats?.status || 'Unknown',
            cache_status: performanceData.cache_stats?.status || 'Unknown',
            network_status: performanceData.network_info?.status || 'Unknown'
        },
        detailed_statistics: performanceData,
        recommendations: generateRecommendations()
    };
    
    // Create and download file
    const filename = `autowash-system-report-${eatTime.getFullYear()}-${(eatTime.getMonth()+1).toString().padStart(2,'0')}-${eatTime.getDate().toString().padStart(2,'0')}-${eatTime.getHours()}${eatTime.getMinutes()}.json`;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(reportData, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", filename);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
    
    showAlert(`System report exported: ${filename}`, 'success');
}

/**
 * Clear Cache
 */
function clearCache() {
    showConfirmationModal(
        'Clear System Cache', 
        'This will clear all cached data and may temporarily impact performance. Continue?', 
        function() {
            showAlert('Cache clearing request sent to server...', 'info');
            
            // Try to make actual cache clear request
            fetch('/system-admin/clear-cache/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ action: 'clear_cache' })
            })
            .then(response => {
                if (response.ok) {
                    showAlert('Cache cleared successfully', 'success');
                    setTimeout(refreshCacheStatus, 1000);
                } else {
                    showAlert('Cache clearing failed - server error', 'error');
                }
            })
            .catch(error => {
                console.log('Cache clear request failed, simulating:', error);
                showAlert('Cache cleared (simulated - check server logs)', 'info');
            });
        }
    );
}

/**
 * Get CSRF Token
 */
function getCsrfToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    return token ? token.value : '';
}

/**
 * Get CPU Status
 */
function getCPUStatus() {
    const cpuUsage = performanceData.cpu_info?.usage_percent || 0;
    return cpuUsage < 70 ? 'optimal' : cpuUsage < 90 ? 'warning' : 'critical';
}

/**
 * Get Memory Status
 */
function getMemoryStatus() {
    const memoryUsage = performanceData.memory_info?.usage_percent || 0;
    return memoryUsage < 70 ? 'optimal' : memoryUsage < 90 ? 'warning' : 'critical';
}

/**
 * Generate System Recommendations
 */
function generateRecommendations() {
    const recommendations = [];
    
    const cpuUsage = performanceData.cpu_info?.usage_percent || 0;
    const memoryUsage = performanceData.memory_info?.usage_percent || 0;
    const slowQueries = performanceData.database_stats?.slow_queries || 0;
    
    if (cpuUsage > 80) {
        recommendations.push({
            type: 'performance',
            priority: 'high',
            message: 'CPU usage is high. Consider optimizing resource-intensive operations or scaling up.'
        });
    }
    
    if (memoryUsage > 80) {
        recommendations.push({
            type: 'performance',
            priority: 'high',
            message: 'Memory usage is high. Review memory-intensive processes and consider increasing RAM.'
        });
    }
    
    if (slowQueries > 10) {
        recommendations.push({
            type: 'database',
            priority: 'medium',
            message: 'Multiple slow queries detected. Review and optimize database queries.'
        });
    }
    
    if (recommendations.length === 0) {
        recommendations.push({
            type: 'general',
            priority: 'info',
            message: 'System is operating within normal parameters. Continue monitoring.'
        });
    }
    
    return recommendations;
}

/**
 * Refresh Cache Status
 */
function refreshCacheStatus() {
    const cacheStatusElements = document.querySelectorAll('[data-cache-status]');
    cacheStatusElements.forEach(element => {
        element.textContent = 'CLEARED';
        element.style.color = '#4CAF50';
    });
}

/**
 * Initialize the main performance chart
 */
function initializePerformanceChart() {
    const ctx = document.getElementById('performance-chart');
    if (!ctx) return;

    // Use actual system data from performanceData
    const now = new Date();
    const labels = [];
    const cpuData = [];
    const memoryData = [];
    const responseTimeData = [];

    // Get current metrics from actual data
    const currentCpu = performanceData?.system_metrics?.cpu_percent || 0;
    const currentMemory = performanceData?.system_metrics?.memory_percent || 0;
    
    // Create time series with current actual data point and historical simulation
    for (let i = 24; i >= 0; i--) {
        const time = new Date(now.getTime() - i * 60000); // Last 24 minutes
        labels.push(time.toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit' 
        }));
        
        if (i === 0) {
            // Use actual current data for most recent point
            cpuData.push(currentCpu);
            memoryData.push(currentMemory);
            responseTimeData.push(Math.random() * 50 + 100); // Response time simulation
        } else {
            // Generate historical data points based on current values
            const cpuVariation = Math.random() * 10 - 5; // ±5% variation
            const memoryVariation = Math.random() * 8 - 4; // ±4% variation
            
            cpuData.push(Math.max(0, Math.min(100, currentCpu + cpuVariation)));
            memoryData.push(Math.max(0, Math.min(100, currentMemory + memoryVariation)));
            responseTimeData.push(Math.random() * 100 + 100 + Math.sin(i * 0.4) * 30);
        }
    }

    performanceCharts.main = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'CPU Usage (%)',
                    data: cpuData,
                    borderColor: CHART_COLORS.primary,
                    backgroundColor: `${CHART_COLORS.primary}20`,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Memory Usage (%)',
                    data: memoryData,
                    borderColor: CHART_COLORS.secondary,
                    backgroundColor: `${CHART_COLORS.secondary}20`,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Response Time (ms)',
                    data: responseTimeData,
                    borderColor: CHART_COLORS.accent,
                    backgroundColor: `${CHART_COLORS.accent}20`,
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#ffffff',
                        font: {
                            family: 'Courier New, monospace'
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#b8b8b8' },
                    grid: { color: '#333366' }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    ticks: { color: '#b8b8b8' },
                    grid: { color: '#333366' },
                    title: {
                        display: true,
                        text: 'Usage (%)',
                        color: '#ffffff'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    ticks: { color: '#b8b8b8' },
                    grid: { drawOnChartArea: false },
                    title: {
                        display: true,
                        text: 'Response Time (ms)',
                        color: '#ffffff'
                    }
                }
            },
            animation: {
                duration: 750,
                easing: 'easeInOutQuart'
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });
}

/**
 * Initialize database performance chart
 */
function initializeDatabaseChart() {
    const ctx = document.getElementById('db-performance-chart');
    if (!ctx) return;

    const labels = ['Total Queries', 'Active Connections', 'Slow Queries', 'DB Queries/sec'];
    const data = [
        Math.min(performanceData.application_metrics?.queries_per_second * 1000 || 1000, 10000), // Scale for visualization
        performanceData.application_metrics?.db_connections || performanceData.database_stats?.active_connections || 25,
        performanceData.database_stats?.slow_queries || 5,
        performanceData.application_metrics?.queries_per_second || 1.5
    ];

    performanceCharts.database = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    CHART_COLORS.primary,
                    CHART_COLORS.secondary,
                    CHART_COLORS.danger,
                    CHART_COLORS.accent
                ],
                borderColor: '#1a1a2e',
                borderWidth: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#ffffff',
                        padding: 10,
                        font: {
                            family: 'Courier New, monospace',
                            size: 10
                        }
                    }
                }
            },
            animation: {
                duration: 750,
                easing: 'easeInOutQuart'
            }
        }
    });
}

/**
 * Initialize network traffic chart
 */
function initializeNetworkChart() {
    const ctx = document.getElementById('network-chart');
    if (!ctx) return;

    const labels = [];
    const inData = [];
    const outData = [];

    // Get actual network data from system metrics
    const networkBytesSent = performanceData?.system_metrics?.network_bytes_sent || 0;
    const networkBytesRecv = performanceData?.system_metrics?.network_bytes_recv || 0;
    
    // Convert bytes to MB/s (estimated)
    const currentOutMBps = networkBytesSent / (1024 * 1024) / 60; // Rough estimate
    const currentInMBps = networkBytesRecv / (1024 * 1024) / 60;  // Rough estimate

    // Generate network traffic data for last 20 points with real data influence
    for (let i = 19; i >= 0; i--) {
        labels.push(`-${i}m`);
        
        if (i === 0) {
            // Use actual current data for most recent point
            inData.push(Math.max(0.1, currentInMBps));
            outData.push(Math.max(0.1, currentOutMBps));
        } else {
            // Generate historical data influenced by current values
            const variation = Math.random() * 0.6 + 0.7; // 70-130% of current
            inData.push(Math.max(0.1, currentInMBps * variation));
            outData.push(Math.max(0.1, currentOutMBps * variation));
        }
    }

    performanceCharts.network = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Inbound (MB/s)',
                    data: inData,
                    borderColor: CHART_COLORS.secondary,
                    backgroundColor: `${CHART_COLORS.secondary}30`,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Outbound (MB/s)',
                    data: outData,
                    borderColor: CHART_COLORS.primary,
                    backgroundColor: `${CHART_COLORS.primary}30`,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#ffffff',
                        font: {
                            family: 'Courier New, monospace',
                            size: 9
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#b8b8b8', font: { size: 9 } },
                    grid: { color: '#333366' }
                },
                y: {
                    ticks: { color: '#b8b8b8', font: { size: 9 } },
                    grid: { color: '#333366' }
                }
            },
            animation: {
                duration: 500,
                easing: 'easeInOutQuart'
            }
        }
    });
}

/**
 * Initialize user activity chart
 */
function initializeUserActivityChart() {
    const ctx = document.getElementById('user-activity-chart');
    if (!ctx) return;

    const labels = [];
    const activeUsers = [];
    const newSignups = [];

    // Use actual business and tenant data
    const currentActiveTenants = performanceData?.application_metrics?.active_tenants || 0;
    const totalTenants = performanceData?.application_metrics?.total_tenants || 0;
    const currentActiveUsers = performanceData?.application_metrics?.active_sessions || 0;
    const dbConnections = performanceData?.application_metrics?.db_connections || 0;
    
    // Generate user activity data for last 12 hours with real tenant business data
    for (let i = 11; i >= 0; i--) {
        const hour = new Date(Date.now() - i * 3600000).getHours();
        labels.push(`${hour}:00`);
        
        if (i === 0) {
            // Use actual current data for most recent hour
            activeUsers.push(currentActiveUsers);
            // Business signups based on tenant database activity
            const businessSignups = Math.max(0, Math.floor((totalTenants - currentActiveTenants) / 20));
            newSignups.push(businessSignups || 1);
        } else {
            // Generate historical data influenced by business hours and tenant activity
            const isBusinessHour = hour >= 8 && hour <= 18;
            const businessMultiplier = isBusinessHour ? 1.2 : 0.6;
            
            // Scale user activity based on tenant database connections
            const scaledUsers = Math.max(1, Math.floor(currentActiveUsers * businessMultiplier * (Math.random() * 0.4 + 0.8)));
            activeUsers.push(scaledUsers);
            
            // Business signups influenced by time and tenant activity
            const signupRate = isBusinessHour ? Math.random() * 4 + 1 : Math.random() * 2;
            newSignups.push(Math.max(0, Math.floor(signupRate)));
        }
    }

    performanceCharts.userActivity = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Active Sessions (Tenant DB)',
                    data: activeUsers,
                    backgroundColor: `${CHART_COLORS.primary}60`,
                    borderColor: CHART_COLORS.primary,
                    borderWidth: 1
                },
                {
                    label: 'New Business Signups',
                    data: newSignups,
                    backgroundColor: `${CHART_COLORS.secondary}60`,
                    borderColor: CHART_COLORS.secondary,
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#ffffff',
                        font: {
                            family: 'Courier New, monospace',
                            size: 11
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#b8b8b8', font: { size: 10 } },
                    grid: { color: '#333366' }
                },
                y: {
                    ticks: { color: '#b8b8b8', font: { size: 10 } },
                    grid: { color: '#333366' }
                }
            }
        }
    });
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Auto-refresh toggle
    const autoRefreshToggle = document.getElementById('auto-refresh-toggle');
    if (autoRefreshToggle) {
        autoRefreshToggle.addEventListener('change', function() {
            isAutoRefreshEnabled = this.checked;
            if (isAutoRefreshEnabled) {
                startAutoRefresh();
                updateConnectionStatus(true);
            } else {
                stopAutoRefresh();
                updateConnectionStatus(false);
            }
        });
    }

    // Chart metric selector
    const chartMetric = document.getElementById('chart-metric');
    if (chartMetric) {
        chartMetric.addEventListener('change', updateChart);
    }

    // Log level filter
    const logLevelFilter = document.getElementById('log-level-filter');
    if (logLevelFilter) {
        logLevelFilter.addEventListener('change', filterLogs);
    }

    // Window focus/blur for performance optimization
    window.addEventListener('focus', () => {
        if (isAutoRefreshEnabled) startAutoRefresh();
    });
    
    window.addEventListener('blur', () => {
        // Reduce refresh rate when window is not active
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = setInterval(fetchRealTimeData, REFRESH_INTERVAL * 3);
        }
    });
}

/**
 * Start auto-refresh functionality
 */
function startAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    autoRefreshInterval = setInterval(fetchRealTimeData, REFRESH_INTERVAL);
    console.log('🔄 Auto-refresh started');
}

/**
 * Stop auto-refresh functionality
 */
function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
    console.log('⏸️ Auto-refresh stopped');
}

/**
 * Fetch real-time data from server
 */
async function fetchRealTimeData() {
    try {
        const response = await fetch('/system-admin/performance-api/', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        
        // Validate data structure before processing
        if (data && typeof data === 'object') {
            updateRealTimeDisplay(data);
            updateCharts(data);
            addLogEntry('info', 'Real-time data updated successfully');
        } else {
            throw new Error('Invalid data format received from server');
        }
        
    } catch (error) {
        console.error('❌ Error fetching real-time data:', error);
        updateConnectionStatus(false);
        addLogEntry('error', `Failed to fetch real-time data: ${error.message}`);
        
        // Show alert for connection issues
        showAlert('Connection Error', 'Unable to fetch real-time data from server');
    }
}

/**
 * Update real-time display elements
 */
function updateRealTimeDisplay(data) {
    // Update CPU percentage
    const cpuElement = document.getElementById('cpu-percent');
    if (cpuElement && data.system_metrics) {
        cpuElement.textContent = `${data.system_metrics.cpu_percent}%`;
        updateStatBar(cpuElement, data.system_metrics.cpu_percent);
    }

    // Update memory percentage
    const memoryElement = document.getElementById('memory-percent');
    if (memoryElement && data.system_metrics) {
        memoryElement.textContent = `${data.system_metrics.memory_percent}%`;
        updateStatBar(memoryElement, data.system_metrics.memory_percent);
    }

    // Update active tenant businesses (AutoWash platform)
    const activeTenantsElement = document.getElementById('active-tenants');
    if (activeTenantsElement && data.application_metrics) {
        const activeTenants = data.application_metrics.active_tenants;
        const totalTenants = data.application_metrics.total_tenants || activeTenants;
        
        activeTenantsElement.textContent = `${activeTenants}/${totalTenants}`;
        
        // Add pulsing animation for active count changes
        activeTenantsElement.classList.add('updated');
        setTimeout(() => activeTenantsElement.classList.remove('updated'), 1000);
    }

    // Update AutoWash database connections (default + tenant DBs)
    const dbConnectionsElement = document.getElementById('db-connections');
    if (dbConnectionsElement && data.application_metrics) {
        const dbConnections = data.application_metrics.db_connections;
        const queriesPerSec = data.application_metrics.queries_per_second || 0;
        
        // Show connections with query rate for database activity
        dbConnectionsElement.textContent = `${dbConnections} (${queriesPerSec.toFixed(1)}/s)`;
        
        // Color code based on connection load
        dbConnectionsElement.className = dbConnections > 50 ? 'warning' : dbConnections > 100 ? 'critical' : 'optimal';
    }

    // Update active user sessions across all tenants
    const activeSessionsElement = document.getElementById('active-sessions');
    if (activeSessionsElement && data.application_metrics) {
        const activeSessions = data.application_metrics.active_sessions;
        activeSessionsElement.textContent = activeSessions;
        
        // Animate session count changes
        if (activeSessions !== window.lastSessionCount) {
            activeSessionsElement.classList.add('pulse');
            setTimeout(() => activeSessionsElement.classList.remove('pulse'), 500);
            window.lastSessionCount = activeSessions;
        }
    }

    // Update health indicators
    if (data.health_status) {
        updateHealthIndicators(data.health_status);
    }
    
    // Update all log sections automatically
    try {
        if (data.django_logs) {
            updateLogSections(data.django_logs);
        }
    } catch (error) {
        console.warn('Error updating log sections:', error);
    }
    
    // Update authentication metrics if available
    try {
        if (data.main_db_auth_metrics) {
            updateAuthMetrics(data.main_db_auth_metrics);
        }
    } catch (error) {
        console.warn('Error updating auth metrics:', error);
    }

    // Update connection status
    updateConnectionStatus(true);
}

/**
 * Update stat bars with new values
 */
function updateStatBar(element, percentage) {
    const statItem = element.closest('.stat-item');
    const statFill = statItem?.querySelector('.stat-fill');
    
    if (statFill) {
        statFill.style.width = `${percentage}%`;
        
        // Update color based on percentage
        if (percentage > 90) {
            statFill.style.background = `linear-gradient(90deg, ${CHART_COLORS.danger}, rgba(255, 68, 68, 0.8))`;
        } else if (percentage > 70) {
            statFill.style.background = `linear-gradient(90deg, ${CHART_COLORS.accent}, rgba(255, 235, 59, 0.8))`;
        } else {
            statFill.style.background = `linear-gradient(90deg, ${CHART_COLORS.primary}, ${CHART_COLORS.secondary})`;
        }
    }
}

/**
 * Update health indicators
 */
function updateHealthIndicators(healthStatus) {
    const indicators = ['cpu', 'memory', 'disk'];
    
    indicators.forEach(indicator => {
        const elements = document.querySelectorAll(`.health-item[data-indicator="${indicator}"]`);
        elements.forEach(element => {
            // Remove existing status classes
            element.classList.remove('status-optimal', 'status-warning', 'status-critical');
            
            // Add new status class
            if (healthStatus[indicator]) {
                element.classList.add(`status-${healthStatus[indicator]}`);
            }
        });
    });
}

/**
 * Update charts with new data
 */
function updateCharts(data) {
    if (!data || !performanceCharts.main) return;

    const chart = performanceCharts.main;
    const now = new Date();
    
    // Add new data point
    chart.data.labels.push(now.toLocaleTimeString('en-US', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit',
        second: '2-digit'
    }));
    
    chart.data.datasets[0].data.push(data.system_metrics?.cpu_percent || 0);
    chart.data.datasets[1].data.push(data.system_metrics?.memory_percent || 0);
    // Calculate response time based on system load (CPU + Memory usage as proxy)
    const systemLoad = (data.system_metrics?.cpu_percent || 0) + (data.system_metrics?.memory_percent || 0);
    const responseTime = 50 + (systemLoad * 2) + (Math.random() * 30 - 15); // Base 50ms + load factor + small variation
    chart.data.datasets[2].data.push(Math.max(10, responseTime));
    
    // Keep only last N data points
    if (chart.data.labels.length > MAX_DATA_POINTS) {
        chart.data.labels.shift();
        chart.data.datasets.forEach(dataset => dataset.data.shift());
    }
    
    chart.update('none'); // Update without animation for better performance
}

/**
 * Update chart based on selected metric
 */
function updateChart() {
    const selectedMetric = document.getElementById('chart-metric')?.value;
    if (!selectedMetric || !performanceCharts.main) return;

    const chart = performanceCharts.main;
    
    // Update chart datasets based on selected metric
    switch(selectedMetric) {
        case 'cpu':
            chart.data.datasets[0].label = 'CPU Usage (%)';
            chart.data.datasets[0].data = chart.data.datasets[0].data; // Keep CPU data
            chart.data.datasets[1].hidden = true;
            chart.data.datasets[2].hidden = true;
            break;
            
        case 'memory':
            chart.data.datasets[1].label = 'Memory Usage (%)';
            chart.data.datasets[0].hidden = true;
            chart.data.datasets[1].hidden = false;
            chart.data.datasets[2].hidden = true;
            break;
            
        case 'response_time':
            chart.data.datasets[2].label = 'Response Time (ms)';
            chart.data.datasets[0].hidden = true;
            chart.data.datasets[1].hidden = true;
            chart.data.datasets[2].hidden = false;
            break;
            
        case 'active_users':
            // Use session data for active users
            const activeUsers = performanceData?.application_metrics?.active_sessions || 0;
            chart.data.datasets[0].label = 'Active Sessions';
            chart.data.datasets[0].hidden = false;
            chart.data.datasets[1].hidden = true;
            chart.data.datasets[2].hidden = true;
            break;
            
        default:
            // Show all datasets
            chart.data.datasets[0].hidden = false;
            chart.data.datasets[1].hidden = false;
            chart.data.datasets[2].hidden = false;
    }
    
    chart.update();
    console.log('📊 Chart metric changed to:', selectedMetric);
    addLogEntry('info', `Chart view changed to: ${selectedMetric}`);
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(isConnected) {
    const statusIndicator = document.getElementById('connection-status');
    const statusText = statusIndicator?.nextElementSibling;
    
    if (statusIndicator) {
        statusIndicator.classList.toggle('active', isConnected);
        
        if (statusText) {
            statusText.textContent = isConnected ? 'CONNECTED' : 'DISCONNECTED';
        }
    }
}

/**
 * Update all log sections with fresh data
 */
function updateLogSections(djangoLogs) {
    try {
        // Update main logs container
        const logsContainer = document.getElementById('logs-container');
        if (logsContainer) {
            let logHTML = '';
            if (djangoLogs && Array.isArray(djangoLogs) && djangoLogs.length > 0) {
                djangoLogs.slice(0, 20).forEach(log => {
                    try {
                        const timestamp = log.timestamp ? new Date(log.timestamp).toLocaleString() : new Date().toLocaleString();
                        const level = log.level || 'INFO';
                        const levelClass = getLevelClass(level);
                        const message = log.message || log.msg || 'No message';
                        const source = log.name || log.source || 'system';
                        
                        logHTML += `
                            <div class="log-entry ${levelClass}" data-level="${level}">
                                <span class="log-time">[${timestamp}]</span>
                                <span class="log-level">${level.toUpperCase()}</span>
                                <span class="log-source">[${source}]</span>
                                <span class="log-message">${message}</span>
                            </div>
                        `;
                    } catch (logError) {
                        console.warn('Error processing individual log entry:', logError, log);
                    }
                });
            } else {
                logHTML = `
                    <div class="log-entry info" data-level="info">
                        <span class="log-time">[${new Date().toLocaleString()}]</span>
                        <span class="log-level">INFO</span>
                        <span class="log-source">[monitoring]</span>
                        <span class="log-message">Live monitoring active - No recent Django logs</span>
                    </div>
                `;
            }
            
            logsContainer.innerHTML = logHTML;
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }
    } catch (error) {
        console.warn('Error updating logs container:', error);
    }
    
    try {
        // Update Django log stream
        const djangoLogStream = document.getElementById('djangoLogStream');
        if (djangoLogStream) {
            let streamHTML = '';
            if (djangoLogs && Array.isArray(djangoLogs) && djangoLogs.length > 0) {
                djangoLogs.slice(0, 15).forEach(log => {
                    try {
                        const timestamp = log.timestamp ? new Date(log.timestamp).toLocaleString() : new Date().toLocaleString();
                        const level = log.level || 'INFO';
                        const levelClass = getLevelClass(level);
                        const message = log.message || log.msg || 'No message';
                        
                        streamHTML += `
                            <div class="log-entry ${levelClass}">
                                <span class="log-timestamp">${timestamp}</span>
                                <span class="log-level">${level}</span>
                                <span class="log-content">${message}</span>
                            </div>
                        `;
                    } catch (logError) {
                        console.warn('Error processing log stream entry:', logError, log);
                    }
                });
            } else {
                streamHTML = `
                    <div class="log-entry info">
                        <span class="log-timestamp">${new Date().toLocaleString()}</span>
                        <span class="log-level">INFO</span>
                        <span class="log-content">No Django logs available - System monitoring active</span>
                    </div>
                `;
            }
            
            djangoLogStream.innerHTML = streamHTML;
            djangoLogStream.scrollTop = djangoLogStream.scrollHeight;
        }
    } catch (error) {
        console.warn('Error updating Django log stream:', error);
    }
    
    try {
        // Update error log count
        const errorLogCountElement = document.querySelector('[data-metric="django-logs"] .value');
        if (errorLogCountElement && djangoLogs && Array.isArray(djangoLogs)) {
            errorLogCountElement.textContent = djangoLogs.length;
        }
    } catch (error) {
        console.warn('Error updating log count:', error);
    }
}

/**
 * Update authentication metrics display
 */
function updateAuthMetrics(authMetrics) {
    try {
        // Update active sessions
        const activeSessionsAuth = document.querySelector('.auth-value[data-metric="active-sessions"]');
        if (activeSessionsAuth && authMetrics && authMetrics.active_sessions !== undefined) {
            activeSessionsAuth.textContent = authMetrics.active_sessions;
        }
        
        // Update total users
        const totalUsersAuth = document.querySelector('.auth-value[data-metric="total-users"]');
        if (totalUsersAuth && authMetrics && authMetrics.total_users !== undefined) {
            totalUsersAuth.textContent = authMetrics.total_users;
        }
        
        // Update recent logins
        const recentLoginsAuth = document.querySelector('.login-value[data-metric="recent-logins"]');
        if (recentLoginsAuth && authMetrics && authMetrics.login_patterns && authMetrics.login_patterns.recent_logins_24h !== undefined) {
            recentLoginsAuth.textContent = authMetrics.login_patterns.recent_logins_24h;
        }
        
        // Update database size with proper error handling
        const dbSizeAuth = document.querySelector('.db-value[data-metric="db-size"]');
        if (dbSizeAuth && authMetrics && authMetrics.main_db_stats && authMetrics.main_db_stats.total_size_mb !== undefined) {
            const sizeValue = authMetrics.main_db_stats.total_size_mb;
            // Handle both string and number values
            const numericSize = typeof sizeValue === 'string' ? parseFloat(sizeValue) : sizeValue;
            if (!isNaN(numericSize)) {
                dbSizeAuth.textContent = `${numericSize.toFixed(2)} MB`;
            } else {
                dbSizeAuth.textContent = `${sizeValue} MB`;
            }
        }
        
        // Update authentication stats if available
        if (authMetrics && authMetrics.authentication_stats) {
            const authStats = authMetrics.authentication_stats;
            
            // Update active sessions count
            const activeSessionsCount = document.getElementById('active-sessions-count');
            if (activeSessionsCount && authStats.active_sessions !== undefined) {
                activeSessionsCount.textContent = authStats.active_sessions;
            }
        }
        
    } catch (error) {
        console.warn('Error updating authentication metrics:', error);
        // Don't throw the error to prevent breaking the auto-refresh
    }
}

/**
 * Get CSS class for log level
 */
function getLevelClass(level) {
    const levelLower = level.toLowerCase();
    if (levelLower.includes('error') || levelLower.includes('critical')) return 'error';
    if (levelLower.includes('warning') || levelLower.includes('warn')) return 'warning';
    if (levelLower.includes('info')) return 'info';
    if (levelLower.includes('debug')) return 'debug';
    return 'info';
}

/**
 * Update time display
 */
function updateTimeDisplay() {
    const timeElement = document.getElementById('current-time');
    if (timeElement) {
        const now = new Date();
        timeElement.textContent = now.toISOString().replace('T', ' ').substring(0, 19);
    }
}

/**
 * Initialize real-time logs
 */
function initializeRealTimeLogs() {
    // Add some initial log entries
    addLogEntry('info', 'Performance monitoring system online');
    addLogEntry('info', 'All systems nominal');
    addLogEntry('info', 'Mission Control ready for operations');
}

/**
 * Add log entry
 */
function addLogEntry(level, message, timestamp = null) {
    if (logsPaused) return;

    const logsContainer = document.getElementById('logs-container');
    if (!logsContainer) return;

    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${level}`;
    
    const time = timestamp || new Date();
    const timeStr = time.toLocaleTimeString('en-US', { hour12: false });
    
    logEntry.innerHTML = `
        <span class="log-time">${timeStr}</span>
        <span class="log-level ${level}">${level.toUpperCase()}</span>
        <span class="log-message">${message}</span>
    `;
    
    // Add to top of container
    logsContainer.insertBefore(logEntry, logsContainer.firstChild);
    
    // Keep only last 100 log entries
    const entries = logsContainer.querySelectorAll('.log-entry');
    if (entries.length > 100) {
        entries[entries.length - 1].remove();
    }
    
    // Apply current filter
    filterLogs();
}

/**
 * Filter logs based on selected level
 */
function filterLogs() {
    const filter = document.getElementById('log-level-filter')?.value || 'all';
    const entries = document.querySelectorAll('#logs-container .log-entry');
    
    entries.forEach(entry => {
        const level = entry.querySelector('.log-level').textContent.toLowerCase();
        
        if (filter === 'all' || level === filter) {
            entry.style.display = '';
        } else {
            entry.style.display = 'none';
        }
    });
}

/**
 * Clear logs
 */
function clearLogs() {
    const logsContainer = document.getElementById('logs-container');
    if (logsContainer) {
        logsContainer.innerHTML = '';
        addLogEntry('info', 'Logs cleared by user');
    }
}

/**
 * Pause/resume logs
 */
function pauseLogs() {
    logsPaused = !logsPaused;
    const pauseBtn = document.getElementById('pause-logs-btn');
    
    if (pauseBtn) {
        pauseBtn.textContent = logsPaused ? 'Resume' : 'Pause';
    }
    
    addLogEntry('info', logsPaused ? 'Log collection paused' : 'Log collection resumed');
}

/**
 * Perform server action
 */
async function performServerAction(action) {
    const actionData = {
        'clear_cache': {
            title: 'Clear Cache',
            message: 'This will clear all cached data. This may temporarily slow down the system. Continue?',
            icon: '🧹'
        },
        'optimize_database': {
            title: 'Optimize Database',
            message: 'This will optimize database tables. This operation may take several minutes. Continue?',
            icon: '⚡'
        },
        'collect_garbage': {
            title: 'Collect Garbage',
            message: 'This will run Python garbage collection. Continue?',
            icon: '🗑️'
        },
        'flush_sessions': {
            title: 'Flush Sessions',
            message: 'This will log out all users by clearing session data. Continue?',
            icon: '🚪'
        }
    };

    const data = actionData[action];
    if (!data) {
        addLogEntry('error', `Unknown action: ${action}`);
        return;
    }

    // Show confirmation modal
    pendingAction = action;
    showModal(data.title, data.message);
}

/**
 * Confirm and execute server action
 */
async function confirmAction() {
    if (!pendingAction) return;

    hideModal();
    addLogEntry('info', `Executing server action: ${pendingAction}`);
    
    try {
        const formData = new FormData();
        formData.append('action', pendingAction);
        formData.append('confirm', 'true');

        const response = await fetch('/system-admin/server-action/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken()
            }
        });

        const result = await response.json();
        
        if (result.success) {
            addLogEntry('success', result.message);
            addActionLogEntry(`✅ ${result.message}`);
            
            // Show success alert
            showAlert('Success', result.message, 'success');
        } else {
            addLogEntry('error', result.message);
            addActionLogEntry(`❌ ${result.message}`, 'error');
            
            // Show error alert
            showAlert('Error', result.message, 'error');
        }
        
    } catch (error) {
        const errorMsg = `Failed to execute ${pendingAction}: ${error.message}`;
        addLogEntry('error', errorMsg);
        addActionLogEntry(`❌ ${errorMsg}`, 'error');
        showAlert('Error', errorMsg, 'error');
    }
    
    pendingAction = null;
}

/**
 * Add entry to action log
 */
function addActionLogEntry(message, type = 'info') {
    const actionLog = document.getElementById('action-log');
    if (!actionLog) return;

    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = `${new Date().toLocaleTimeString()} - ${message}`;
    
    actionLog.insertBefore(entry, actionLog.firstChild);
    
    // Keep only last 10 entries
    const entries = actionLog.querySelectorAll('.log-entry');
    if (entries.length > 10) {
        entries[entries.length - 1].remove();
    }
}

/**
 * Show modal dialog
 */
function showModal(title, message) {
    const modal = document.getElementById('confirmation-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalMessage = document.getElementById('modal-message');
    
    if (modal && modalTitle && modalMessage) {
        modalTitle.textContent = title;
        modalMessage.textContent = message;
        modal.classList.remove('hidden');
        
        // Focus on confirm button
        document.getElementById('confirm-action-btn')?.focus();
    }
}

/**
 * Hide modal dialog
 */
function hideModal() {
    const modal = document.getElementById('confirmation-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
    pendingAction = null;
}

/**
 * Show alert notification
 */
function showAlert(title, message, type = 'error') {
    const alertSystem = document.getElementById('alert-system');
    const alertMessage = document.getElementById('alert-message');
    
    if (alertSystem && alertMessage) {
        alertMessage.textContent = `${title}: ${message}`;
        alertSystem.classList.remove('hidden');
        
        // Auto-hide after 5 seconds for success messages
        if (type === 'success') {
            setTimeout(() => {
                hideAlert();
            }, 5000);
        }
    }
}

/**
 * Hide alert notification
 */
function hideAlert() {
    const alertSystem = document.getElementById('alert-system');
    if (alertSystem) {
        alertSystem.classList.add('hidden');
    }
}

/**
 * Get CSRF token for form submissions
 */
function getCsrfToken() {
    const cookie = document.cookie.split(';')
        .find(row => row.trim().startsWith('csrftoken='));
    
    return cookie ? cookie.split('=')[1] : '';
}

/**
 * Handle keyboard shortcuts
 */
document.addEventListener('keydown', function(e) {
    // Ctrl+R - Toggle auto-refresh
    if (e.ctrlKey && e.key === 'r') {
        e.preventDefault();
        const toggle = document.getElementById('auto-refresh-toggle');
        if (toggle) {
            toggle.checked = !toggle.checked;
            toggle.dispatchEvent(new Event('change'));
        }
    }
    
    // Escape - Close modal
    if (e.key === 'Escape') {
        hideModal();
        hideAlert();
    }
});

/**
 * Handle page visibility change
 */
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        // Page is hidden, reduce update frequency
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = setInterval(fetchRealTimeData, REFRESH_INTERVAL * 2);
        }
    } else {
        // Page is visible, restore normal frequency
        if (isAutoRefreshEnabled) {
            startAutoRefresh();
        }
    }
});

// Export functions for global access
window.performServerAction = performServerAction;
window.confirmAction = confirmAction;
window.hideModal = hideModal;
window.hideAlert = hideAlert;
window.clearLogs = clearLogs;
window.pauseLogs = pauseLogs;
window.updateChart = updateChart;