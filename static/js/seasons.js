class AgriVisionDashboard {
    constructor() {
        this.currentSeason = '2023';
        this.compareMode = false;
        this.compareSeason = '2024';
        this.charts = {};
        this.animationFrameId = null;
        
        this.seasonData = {
            '2023': {
                hectares: { achieved: 1250, expected: 1200, unit: 'ha' },
                yield: { achieved: 15.8, expected: 12.0, unit: '%' },
                water: { achieved: 45000, expected: 40000, unit: 'm³' },
                co2: { achieved: 12500, expected: 10000, unit: 'kg' },
                revenue: { achieved: 2.4, expected: 2.0, unit: 'M USD' }
            },
            '2024': {
                hectares: { achieved: 1580, expected: 1450, unit: 'ha' },
                yield: { achieved: 22.3, expected: 18.5, unit: '%' },
                water: { achieved: 67000, expected: 55000, unit: 'm³' },
                co2: { achieved: 18750, expected: 15000, unit: 'kg' },
                revenue: { achieved: 3.8, expected: 3.2, unit: 'M USD' }
            },
            '2025': {
                hectares: { achieved: 890, expected: 1800, unit: 'ha' },
                yield: { achieved: 8.2, expected: 25.0, unit: '%' },
                water: { achieved: 28000, expected: 75000, unit: 'm³' },
                co2: { achieved: 7200, expected: 20000, unit: 'kg' },
                revenue: { achieved: 1.6, expected: 4.5, unit: 'M USD' }
            }
        };

        this.metricConfig = {
            hectares: { icon: '🌾', title: 'Hectares Monitored', color: '#10b981' },
            yield: { icon: '📈', title: 'Yield Increase', color: '#f59e0b' },
            water: { icon: '💧', title: 'Water Saved', color: '#3b82f6' },
            co2: { icon: '🌍', title: 'CO₂ Reduction', color: '#10b981' },
            revenue: { icon: '💵', title: 'Revenue Impact', color: '#8b5cf6' }
        };

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.renderMetrics();
        this.initializeCharts();
        this.startPerformanceMonitoring();
    }

    setupEventListeners() {
        // Season selector buttons
        document.querySelectorAll('.season-btn').forEach(btn => {
            btn.addEventListener('click', this.handleSeasonChange.bind(this));
        });

        // Compare toggle
        const compareToggle = document.getElementById('compareToggle');
        compareToggle?.addEventListener('click', this.toggleCompare.bind(this));
        
        // Compare season selector
        const compareSelect = document.getElementById('compareSeason');
        compareSelect?.addEventListener('change', this.handleCompareSeasonChange.bind(this));

        // Keyboard navigation
        document.addEventListener('keydown', this.handleKeyboard.bind(this));

        // Resize handler for responsive charts
        window.addEventListener('resize', this.debounce(this.handleResize.bind(this), 250));
    }

    handleSeasonChange(e) {
        document.querySelectorAll('.season-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        this.currentSeason = e.target.dataset.season;
        this.renderMetrics();
        this.updateCharts();
    }

    handleCompareSeasonChange(e) {
        this.compareSeason = e.target.value;
        if (this.compareMode) {
            this.renderComparison();
        }
    }

    handleKeyboard(e) {
        if (e.key === 'c' && e.ctrlKey) {
            e.preventDefault();
            this.toggleCompare();
        }
    }

    handleResize() {
        Object.values(this.charts).forEach(chart => {
            if (chart && chart.resize) {
                chart.resize();
            }
        });
    }

    toggleCompare() {
        this.compareMode = !this.compareMode;
        const toggle = document.getElementById('compareToggle');
        const selector = document.getElementById('compareSeason');
        const comparisonSection = document.getElementById('comparisonSection');
        
        toggle?.classList.toggle('active');
        
        if (this.compareMode) {
            selector.style.display = 'block';
            comparisonSection.style.display = 'block';
            this.renderComparison();
        } else {
            selector.style.display = 'none';
            comparisonSection.style.display = 'none';
        }
    }

    renderMetrics() {
        const grid = document.getElementById('metricsGrid');
        if (!grid) return;
        
        grid.innerHTML = '';
        const data = this.seasonData[this.currentSeason];
        
        Object.entries(data).forEach(([key, values], index) => {
            const config = this.metricConfig[key];
            const progress = Math.min((values.achieved / values.expected) * 100, 100);
            const isOverAchieving = values.achieved > values.expected;
            
            const card = this.createMetricCard(key, values, config, progress, isOverAchieving, index);
            grid.appendChild(card);
        });

        this.animateMetricCards();
    }

    createMetricCard(key, values, config, progress, isOverAchieving, index) {
        const card = document.createElement('div');
        card.className = 'metric-card loading';
        card.style.animationDelay = `${index * 0.1}s`;
        
        card.innerHTML = `
            <div class="metric-header">
                <div class="metric-icon" style="background: linear-gradient(135deg, ${config.color}, ${this.lightenColor(config.color, 20)})">
                    ${config.icon}
                </div>
                <div class="metric-title">${config.title}</div>
            </div>
            <div class="metric-values">
                <div class="achieved-value" data-value="${values.achieved}">0 ${values.unit}</div>
                <div class="expected-value">Target: ${this.formatNumber(values.expected)} ${values.unit}</div>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" data-progress="${progress}" style="width: 0%"></div>
            </div>
            <div class="progress-text">
                <span class="trend-indicator ${isOverAchieving ? 'trend-up' : 'trend-down'}">
                    ${isOverAchieving ? '↗' : '↘'} ${progress.toFixed(1)}%
                </span>
            </div>
        `;
        
        return card;
    }

    animateMetricCards() {
        const cards = document.querySelectorAll('.metric-card');
        
        cards.forEach((card, index) => {
            setTimeout(() => {
                card.classList.remove('loading');
                
                // Animate achieved value
                const achievedEl = card.querySelector('.achieved-value');
                const targetValue = parseFloat(achievedEl.dataset.value);
                const unit = achievedEl.textContent.split(' ').slice(-1)[0];
                this.animateNumber(achievedEl, 0, targetValue, 1000, unit);
                
                // Animate progress bar
                const progressEl = card.querySelector('.progress-fill');
                const targetProgress = parseFloat(progressEl.dataset.progress);
                setTimeout(() => {
                    progressEl.style.width = `${targetProgress}%`;
                }, 500);
                
            }, index * 100);
        });
    }

    animateNumber(element, start, end, duration, unit) {
        let startTime = null;
        
        const animate = (currentTime) => {
            if (!startTime) startTime = currentTime;
            const progress = Math.min((currentTime - startTime) / duration, 1);
            
            const current = start + (end - start) * this.easeOutCubic(progress);
            element.textContent = `${this.formatNumber(current)} ${unit}`;
            
            if (progress < 1) {
                this.animationFrameId = requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }

    renderComparison() {
        const grid = document.getElementById('comparisonGrid');
        if (!grid) return;
        
        grid.innerHTML = '';
        
        const currentData = this.seasonData[this.currentSeason];
        const compareData = this.seasonData[this.compareSeason];
        
        Object.entries(currentData).forEach(([key, currentValues]) => {
            const compareValues = compareData[key];
            const config = this.metricConfig[key];
            const difference = ((currentValues.achieved - compareValues.achieved) / compareValues.achieved * 100);
            const isImprovement = difference > 0;
            
            const card = document.createElement('div');
            card.className = 'comparison-card';
            card.innerHTML = `
                <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 10px;">${config.title}</div>
                <div style="font-size: 1.1rem; margin-bottom: 5px; color: var(--text-secondary);">
                    ${this.formatNumber(currentValues.achieved)} vs ${this.formatNumber(compareValues.achieved)} ${currentValues.unit}
                </div>
                <div class="trend-indicator ${isImprovement ? 'trend-up' : 'trend-down'}">
                    ${isImprovement ? '↗' : '↘'} ${Math.abs(difference).toFixed(1)}%
                </div>
            `;
            
            grid.appendChild(card);
        });
    }

    initializeCharts() {
        this.createYieldChart();
        this.createResourceChart();
        this.createAchievementChart();
        this.createEnvironmentChart();
    }

    createYieldChart() {
        const ctx = document.getElementById('yieldChart')?.getContext('2d');
        if (!ctx) return;

        this.charts.yield = new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['2023', '2024', '2025'],
                datasets: [{
                    label: 'Achieved Yield Increase (%)',
                    data: [15.8, 22.3, 8.2],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    tension: 0.4,
                    fill: true,
                    pointBackgroundColor: '#10b981',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 6
                }, {
                    label: 'Expected Yield Increase (%)',
                    data: [12.0, 18.5, 25.0],
                    borderColor: '#6b7280',
                    backgroundColor: 'rgba(107, 114, 128, 0.1)',
                    borderDash: [5, 5],
                    tension: 0.4,
                    pointBackgroundColor: '#6b7280',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 4
                }]
            },
            options: this.getChartOptions('Yield Increase (%)')
        });
    }

    createResourceChart() {
        const ctx = document.getElementById('resourceChart')?.getContext('2d');
        if (!ctx) return;

        this.charts.resource = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['2023', '2024', '2025'],
                datasets: [{
                    label: 'Water Saved (k m³)',
                    data: [45, 67, 28],
                    backgroundColor: 'rgba(59, 130, 246, 0.8)',
                    borderColor: '#3b82f6',
                    borderWidth: 1,
                    borderRadius: 8
                }, {
                    label: 'CO₂ Reduction (k kg)',
                    data: [12.5, 18.75, 7.2],
                    backgroundColor: 'rgba(16, 185, 129, 0.8)',
                    borderColor: '#10b981',
                    borderWidth: 1,
                    borderRadius: 8
                }]
            },
            options: this.getChartOptions('Resource Units (k)')
        });
    }

    createAchievementChart() {
        const ctx = document.getElementById('achievementChart')?.getContext('2d');
        if (!ctx) return;

        const data = this.seasonData[this.currentSeason];
        const achievementPercentages = [
            (data.hectares.achieved / data.hectares.expected * 100),
            (data.yield.achieved / data.yield.expected * 100),
            (data.water.achieved / data.water.expected * 100),
            (data.co2.achieved / data.co2.expected * 100),
            (data.revenue.achieved / data.revenue.expected * 100)
        ];

        this.charts.achievement = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Hectares', 'Yield', 'Water', 'CO₂', 'Revenue'],
                datasets: [{
                    label: 'Achieved (%)',
                    data: achievementPercentages,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.2)',
                    pointBackgroundColor: '#10b981',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    borderWidth: 2
                }, {
                    label: 'Target (100%)',
                    data: [100, 100, 100, 100, 100],
                    borderColor: '#6b7280',
                    backgroundColor: 'rgba(107, 114, 128, 0.1)',
                    borderDash: [5, 5],
                    pointBackgroundColor: '#6b7280',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 1,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#d1d5db',
                            font: {
                                family: 'Inter',
                                size: 12
                            }
                        }
                    }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 150,
                        ticks: {
                            color: '#9ca3af',
                            font: {
                                family: 'Inter'
                            }
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        angleLines: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    }
                }
            }
        });
    }

    createEnvironmentChart() {
        const ctx = document.getElementById('environmentChart')?.getContext('2d');
        if (!ctx) return;

        this.charts.environment = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Water Conservation', 'Carbon Reduction', 'Soil Health', 'Biodiversity'],
                datasets: [{
                    data: [35, 25, 25, 15],
                    backgroundColor: [
                        'rgba(59, 130, 246, 0.8)',
                        'rgba(16, 185, 129, 0.8)',
                        'rgba(245, 158, 11, 0.8)',
                        'rgba(139, 92, 246, 0.8)'
                    ],
                    borderColor: [
                        '#3b82f6',
                        '#10b981',
                        '#f59e0b',
                        '#8b5cf6'
                    ],
                    borderWidth: 2,
                    hoverOffset: 10
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#d1d5db',
                            font: {
                                family: 'Inter',
                                size: 12
                            },
                            padding: 20
                        }
                    }
                }
            }
        });
    }

    getChartOptions(yAxisLabel) {
        return {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#d1d5db',
                        font: {
                            family: 'Inter',
                            size: 12
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: '#9ca3af',
                        font: {
                            family: 'Inter'
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: yAxisLabel,
                        color: '#d1d5db',
                        font: {
                            family: 'Inter',
                            size: 12
                        }
                    },
                    ticks: {
                        color: '#9ca3af',
                        font: {
                            family: 'Inter'
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                }
            }
        };
    }

    updateCharts() {
        if (this.charts.achievement) {
            const data = this.seasonData[this.currentSeason];
            const achievementPercentages = [
                (data.hectares.achieved / data.hectares.expected * 100),
                (data.yield.achieved / data.yield.expected * 100),
                (data.water.achieved / data.water.expected * 100),
                (data.co2.achieved / data.co2.expected * 100),
                (data.revenue.achieved / data.revenue.expected * 100)
            ];
            
            this.charts.achievement.data.datasets[0].data = achievementPercentages;
            this.charts.achievement.update('active');
        }
    }

    // Utility functions
    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toLocaleString();
    }

    lightenColor(color, percent) {
        const num = parseInt(color.replace("#", ""), 16);
        const amt = Math.round(2.55 * percent);
        const R = (num >> 16) + amt;
        const B = (num >> 8 & 0x00FF) + amt;
        const G = (num & 0x0000FF) + amt;
        return "#" + (0x1000000 + (R < 255 ? R < 1 ? 0 : R : 255) * 0x10000 + 
                      (B < 255 ? B < 1 ? 0 : B : 255) * 0x100 + 
                      (G < 255 ? G < 1 ? 0 : G : 255)).toString(16).slice(1);
    }

    easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    startPerformanceMonitoring() {
        // Monitor performance and cleanup animations when needed
        let lastTime = performance.now();
        const monitor = () => {
            const currentTime = performance.now();
            const deltaTime = currentTime - lastTime;
            
            if (deltaTime > 50) { // If frame time is too high
                // Reduce animation complexity
                document.querySelectorAll('.metric-card').forEach(card => {
                    card.style.transition = 'transform 0.2s ease';
                });
            }
            
            lastTime = currentTime;
            requestAnimationFrame(monitor);
        };
        
        requestAnimationFrame(monitor);
    }

    // Cleanup method
    destroy() {
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
        }
        
        Object.values(this.charts).forEach(chart => {
            if (chart && chart.destroy) {
                chart.destroy();
            }
        });
        
        window.removeEventListener('resize', this.handleResize);
        document.removeEventListener('keydown', this.handleKeyboard);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.agriDashboard = new AgriVisionDashboard();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.agriDashboard) {
        window.agriDashboard.destroy();
    }
});