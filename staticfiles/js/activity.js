class AgrivisionApp {
    constructor() {
        this.currentDate = new Date();
        this.selectedDate = null;
        this.activities = {
            // Sample data
            '2025-08-15': [
                {
                    type: 'planting',
                    field: 'North Field A',
                    crop: 'Hybrid Corn XYZ123',
                    description: 'Planted hybrid corn variety with improved drought resistance. Used precision planting equipment for optimal spacing.',
                    duration: 6
                }
            ],
            '2025-08-18': [
                {
                    type: 'irrigation',
                    field: 'South Field B',
                    crop: 'Soybeans',
                    description: 'Performed maintenance on drip irrigation system. Replaced damaged emitters and checked water pressure throughout the field.',
                    duration: 3
                }
            ],
            '2025-08-20': [
                {
                    type: 'harvest',
                    field: 'East Field C',
                    crop: 'Winter Wheat',
                    description: 'Harvested winter wheat crop with excellent yield. Moisture content at optimal levels for storage.',
                    duration: 8
                },
                {
                    type: 'maintenance',
                    field: 'Equipment Barn',
                    crop: 'John Deere Tractor',
                    description: 'Routine maintenance on primary tractor. Changed oil, filters, and performed safety inspection.',
                    duration: 2.5
                }
            ]
        };

        this.init();
    }

    init() {
        this.bindEvents();
        this.setDefaultDate();
        this.renderCalendar();
        this.renderActivitiesList();
    }

    bindEvents() {
        // Calendar navigation
        document.getElementById('prevMonth').addEventListener('click', () => this.changeMonth(-1));
        document.getElementById('nextMonth').addEventListener('click', () => this.changeMonth(1));

        // Form submission
        document.getElementById('activityForm').addEventListener('submit', (e) => this.handleFormSubmit(e));
    }

    setDefaultDate() {
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('activityDate').value = today;
    }

    changeMonth(direction) {
        this.currentDate.setMonth(this.currentDate.getMonth() + direction);
        this.renderCalendar();
    }

    renderCalendar() {
        const year = this.currentDate.getFullYear();
        const month = this.currentDate.getMonth();

        // Update month/year display
        document.getElementById('monthYear').textContent = 
            new Date(year, month).toLocaleDateString('en-US', { 
                month: 'long', 
                year: 'numeric' 
            });

        const firstDay = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const daysInPrevMonth = new Date(year, month, 0).getDate();

        const calendarGrid = document.getElementById('calendarGrid');
        
        // Clear existing days (keep headers)
        const dayHeaders = calendarGrid.querySelectorAll('.day-header');
        calendarGrid.innerHTML = '';
        dayHeaders.forEach(header => calendarGrid.appendChild(header));

        // Previous month's trailing days
        for (let i = firstDay - 1; i >= 0; i--) {
            const day = daysInPrevMonth - i;
            const dayCell = this.createDayCell(day, 'other-month', year, month - 1);
            calendarGrid.appendChild(dayCell);
        }

        // Current month days
        for (let day = 1; day <= daysInMonth; day++) {
            const dayCell = this.createDayCell(day, 'current-month', year, month);
            calendarGrid.appendChild(dayCell);
        }

        // Next month's leading days
        const totalCells = calendarGrid.children.length - 7; // Subtract headers
        const remainingCells = 42 - totalCells; // 6 weeks * 7 days - headers
        for (let day = 1; day <= remainingCells; day++) {
            const dayCell = this.createDayCell(day, 'other-month', year, month + 1);
            calendarGrid.appendChild(dayCell);
        }
    }

    createDayCell(day, monthType, year, month) {
        const dayCell = document.createElement('div');
        dayCell.className = `day-cell ${monthType}`;
        
        const dayNumber = document.createElement('div');
        dayNumber.className = 'day-number';
        dayNumber.textContent = day;
        dayCell.appendChild(dayNumber);

        const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        
        // Add activity dots
        if (this.activities[dateKey]) {
            const dotsContainer = document.createElement('div');
            dotsContainer.className = 'activity-dots';
            
            this.activities[dateKey].forEach(activity => {
                const dot = document.createElement('span');
                dot.className = `activity-dot ${activity.type}`;
                dotsContainer.appendChild(dot);
            });
            
            dayCell.appendChild(dotsContainer);
        }

        // Add click event
        dayCell.addEventListener('click', () => {
            document.querySelectorAll('.day-cell').forEach(cell => 
                cell.classList.remove('selected')
            );
            dayCell.classList.add('selected');
            this.selectedDate = dateKey;
            document.getElementById('activityDate').value = dateKey;
        });

        return dayCell;
    }

    handleFormSubmit(e) {
        e.preventDefault();

        const formData = {
            date: document.getElementById('activityDate').value,
            type: document.getElementById('activityType').value,
            field: document.getElementById('fieldSection').value,
            crop: document.getElementById('cropType').value,
            description: document.getElementById('description').value,
            duration: parseFloat(document.getElementById('duration').value) || 0
        };

        this.addActivity(formData.date, formData);
        this.resetForm();
    }

    addActivity(dateKey, activityData) {
        if (!this.activities[dateKey]) {
            this.activities[dateKey] = [];
        }
        
        this.activities[dateKey].push({
            type: activityData.type,
            field: activityData.field,
            crop: activityData.crop,
            description: activityData.description,
            duration: activityData.duration
        });

        this.renderCalendar();
        this.renderActivitiesList();
    }

    resetForm() {
        document.getElementById('activityForm').reset();
        this.setDefaultDate();
    }

    renderActivitiesList() {
        const activitiesList = document.getElementById('activitiesList');
        const allActivities = [];

        // Flatten activities with dates
        Object.keys(this.activities).forEach(date => {
            this.activities[date].forEach(activity => {
                allActivities.push({ ...activity, date });
            });
        });

        // Sort by date (most recent first)
        allActivities.sort((a, b) => new Date(b.date) - new Date(a.date));

        if (allActivities.length === 0) {
            activitiesList.innerHTML = `
                <div class="empty-state">
                    <div class="empty-message">No activities recorded yet</div>
                    <p class="empty-description">Start by adding your first field activity above.</p>
                </div>
            `;
            return;
        }

        activitiesList.innerHTML = allActivities.map(activity => this.createActivityHTML(activity)).join('');
    }

    createActivityHTML(activity) {
        const formattedDate = new Date(activity.date).toLocaleDateString('en-US', {
            weekday: 'short',
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });

        return `
            <div class="activity-item">
                <div class="activity-header">
                    <span class="activity-badge ${activity.type}">${activity.type}</span>
                    <div class="activity-date">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M8 2v4"/>
                            <path d="M16 2v4"/>
                            <rect width="18" height="18" x="3" y="4" rx="2"/>
                            <path d="M3 10h18"/>
                        </svg>
                        ${formattedDate}
                    </div>
                </div>
                
                <div class="activity-details">
                    <div class="activity-field">
                        <div class="field-location">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>
                                <circle cx="12" cy="10" r="3"/>
                            </svg>
                            ${activity.field}
                        </div>
                        <div class="field-crop">
                            <strong>${activity.crop}</strong>
                        </div>
                        ${activity.duration > 0 ? `
                            <div class="activity-duration">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="12" cy="12" r="10"/>
                                    <polyline points="12,6 12,12 16,14"/>
                                </svg>
                                ${activity.duration}h
                            </div>
                        ` : ''}
                    </div>
                    
                    ${activity.description ? `
                        <p class="activity-description">${activity.description}</p>
                    ` : ''}
                </div>
            </div>
        `;
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new AgrivisionApp();
});