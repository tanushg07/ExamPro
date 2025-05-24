// Common JavaScript functions for the Exam Management System

// Auto-save form data to localStorage
function autoSaveForm(formId, saveKey, intervalMs = 30000) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    // Check for saved data and restore it
    const savedData = localStorage.getItem(saveKey);
    if (savedData) {
        const formData = JSON.parse(savedData);
        Object.keys(formData).forEach(name => {
            const input = form.elements[name];
            if (input) {
                if (input.type === 'checkbox' || input.type === 'radio') {
                    input.checked = formData[name];
                } else {
                    input.value = formData[name];
                }
            }
        });
    }
    
    // Set up auto-save at interval
    setInterval(() => {
        const data = {};
        Array.from(form.elements).forEach(input => {
            if (input.name) {
                if (input.type === 'checkbox' || input.type === 'radio') {
                    data[input.name] = input.checked;
                } else {
                    data[input.name] = input.value;
                }
            }
        });
        localStorage.setItem(saveKey, JSON.stringify(data));
    }, intervalMs);
    
    // Clear saved data on form submission
    form.addEventListener('submit', () => {
        localStorage.removeItem(saveKey);
    });
}

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Bootstrap tooltips 
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(() => {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});

// Format exam timer
function formatTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    return [
        hours.toString().padStart(2, '0'),
        minutes.toString().padStart(2, '0'),
        secs.toString().padStart(2, '0')
    ].join(':');
}

// Toggle password visibility
function togglePasswordVisibility(inputId, toggleBtnId) {
    const passwordInput = document.getElementById(inputId);
    const toggleBtn = document.getElementById(toggleBtnId);
    
    if (passwordInput && toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            
            // Update button text
            toggleBtn.textContent = type === 'password' ? 'Show' : 'Hide';
        });
    }
}

// Confirm action with custom modal
function confirmAction(title, message, confirmBtnText, cancelBtnText, onConfirm) {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'confirmModal';
    modal.setAttribute('tabindex', '-1');
    modal.setAttribute('aria-labelledby', 'confirmModalLabel');
    modal.setAttribute('aria-hidden', 'true');
    
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="confirmModalLabel">${title}</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    ${message}
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${cancelBtnText || 'Cancel'}</button>
                    <button type="button" class="btn btn-primary" id="confirmActionBtn">${confirmBtnText || 'Confirm'}</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    const modalElement = new bootstrap.Modal(modal);
    modalElement.show();
    
    document.getElementById('confirmActionBtn').addEventListener('click', () => {
        onConfirm();
        modalElement.hide();
        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    });
    
    modal.addEventListener('hidden.bs.modal', () => {
        document.body.removeChild(modal);
    });
}

// Exam timer with auto-submit
function initExamTimer(timeLimit, formId, warningThreshold = 300) {
    const timerDisplay = document.getElementById('exam-timer');
    const examForm = document.getElementById(formId);
    
    if (!timerDisplay || !examForm) return;
    
    let secondsRemaining = timeLimit;
    let timerInterval;
    
    // Function to update the timer display
    function updateTimer() {
        secondsRemaining--;
        
        // Update the display
        timerDisplay.textContent = formatTime(secondsRemaining);
        
        // Add warning class when time is running low
        if (secondsRemaining <= warningThreshold) {
            timerDisplay.classList.add('text-danger');
            timerDisplay.classList.add('fw-bold');
            
            // Flash the timer when less than 1 minute remains
            if (secondsRemaining <= 60) {
                timerDisplay.classList.toggle('opacity-50');
            }
        }
        
        // Show warning at 5 minutes remaining
        if (secondsRemaining === warningThreshold) {
            const warningToast = new bootstrap.Toast(document.getElementById('time-warning-toast'));
            warningToast.show();
            
            // Also send notification if possible
            if ('Notification' in window && Notification.permission === 'granted') {
                new Notification('Exam Time Warning', {
                    body: 'You have 5 minutes remaining in your exam.',
                    icon: '/static/images/favicon.ico'
                });
            }
        }
        
        // Auto-submit when time is up
        if (secondsRemaining <= 0) {
            clearInterval(timerInterval);
            timerDisplay.textContent = "Time's up!";
            
            // Show submission message
            const submissionMessage = document.createElement('div');
            submissionMessage.className = 'alert alert-warning mt-3';
            submissionMessage.innerHTML = '<strong>Time\'s up!</strong> Your exam is being submitted...';
            document.querySelector('.container').prepend(submissionMessage);
            
            // Create hidden input to mark as auto-submitted
            const autoSubmitField = document.createElement('input');
            autoSubmitField.type = 'hidden';
            autoSubmitField.name = 'auto_submitted';
            autoSubmitField.value = 'true';
            examForm.appendChild(autoSubmitField);
            
            // Submit the form after a brief delay to allow user to see the message
            setTimeout(() => {
                examForm.submit();
            }, 1500);
        }
    }
    
    // Start the timer
    timerInterval = setInterval(updateTimer, 1000);
    
    // Save timer state in localStorage to prevent refresh cheating
    window.addEventListener('beforeunload', () => {
        localStorage.setItem('exam_timer_end', (Date.now() + (secondsRemaining * 1000)));
    });
    
    // Check if there's a saved timer state
    const savedEndTime = localStorage.getItem('exam_timer_end');
    if (savedEndTime) {
        const remainingMs = parseInt(savedEndTime) - Date.now();
        if (remainingMs > 0) {
            secondsRemaining = Math.floor(remainingMs / 1000);
        } else {
            secondsRemaining = 0;
            updateTimer(); // Force submission
        }
    }
    
    // Update the initial display
    timerDisplay.textContent = formatTime(secondsRemaining);
}

// Function to check if an exam is within its availability window
function checkExamAvailability(startTime, endTime, elementId) {
    const now = new Date();
    const start = startTime ? new Date(startTime) : null;
    const end = endTime ? new Date(endTime) : null;
    const messageElement = document.getElementById(elementId);
    
    if (!messageElement) return;
    
    if (start && now < start) {
        // Exam not yet available
        messageElement.innerHTML = `<div class="alert alert-warning">
            <i class="bi bi-clock me-2"></i>
            This exam will be available starting ${start.toLocaleString()}.
        </div>`;
        return false;
    }
    
    if (end && now > end) {
        // Exam has ended
        messageElement.innerHTML = `<div class="alert alert-danger">
            <i class="bi bi-exclamation-triangle me-2"></i>
            This exam is no longer available. It ended on ${end.toLocaleString()}.
        </div>`;
        return false;
    }
    
    if (end) {
        // Exam is available but has end time
        const hoursRemaining = Math.floor((end - now) / (1000 * 60 * 60));
        
        if (hoursRemaining < 24) {
            messageElement.innerHTML = `<div class="alert alert-info">
                <i class="bi bi-alarm me-2"></i>
                This exam will close in ${hoursRemaining} hour${hoursRemaining !== 1 ? 's' : ''}.
            </div>`;
        }
    }
    
    return true;
}
